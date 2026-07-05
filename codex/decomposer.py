from __future__ import annotations

import json

from codex.adapters.base import BaseLLMAdapter
from codex.models import ComplexityAssessment, ComplexityLevel, SubTask, TaskDAG

DECOMPOSER_SYSTEM_PROMPT = """\
You are a task decomposition engine. Given a complex user requirement, you must break it down into a list of sub-tasks that form a Directed Acyclic Graph (DAG).

Rules:
1. Each sub-task must be a concrete, actionable step
2. Dependencies must form a valid DAG (no cycles, no self-references)
3. Independent tasks (no dependencies) can run in parallel
4. Tasks that depend on another task's output must list that task's id in dependencies
5. The final task should aggregate or synthesize results

Return ONLY a JSON array with no other text:

[
  {
    "id": "1",
    "description": "task description in user's language",
    "dependencies": []
  },
  {
    "id": "2",
    "description": "another task",
    "dependencies": ["1"]
  }
]

Important:
- Use sequential numeric IDs: "1", "2", "3", ...
- "dependencies" lists IDs of tasks that MUST complete before this one
- Keep descriptions specific and actionable
- 3-8 sub-tasks is typical; don't over-decompose
"""

DECOMPOSER_USER_TEMPLATE = """\
Complexity: {level} ({estimated_subtasks} estimated sub-tasks)
Type: {task_type}

Requirement:
{requirement}

Context (if any):
{context}

Break this requirement into a DAG of sub-tasks."""


class TaskDecomposer:
    """Breaks complex requirements into a DAG of sub-tasks."""

    def __init__(self, adapter: BaseLLMAdapter):
        self._adapter = adapter

    async def decompose(
        self,
        requirement: str,
        assessment: ComplexityAssessment,
        context: str = "",
    ) -> TaskDAG:
        # Simple tasks don't need decomposition
        if assessment.level == ComplexityLevel.SIMPLE:
            return TaskDAG(
                tasks=[
                    SubTask(
                        id="1",
                        description=requirement,
                        dependencies=[],
                    )
                ]
            )

        user_message = DECOMPOSER_USER_TEMPLATE.format(
            level=assessment.level.value,
            estimated_subtasks=assessment.estimated_subtasks,
            task_type=assessment.task_type.value,
            requirement=requirement,
            context=context or "None",
        )

        messages = [
            {"role": "system", "content": DECOMPOSER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw = await self._adapter.chat(messages, temperature=0.3, response_format={"type": "json_object"})
        return self._parse(raw)

    def _parse(self, raw: str) -> TaskDAG:
        raw = raw.strip()
        # Handle json_object wrapping: sometimes returns {"tasks": [...]}
        # Strip markdown fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return TaskDAG(tasks=[])

        # Handle {"tasks": [...]} wrapping
        if isinstance(data, dict):
            tasks_data = data.get("tasks", data.get("subtasks", []))
            if not tasks_data:
                # Maybe it's a single task object
                tasks_data = [data] if "id" in data else []
        elif isinstance(data, list):
            tasks_data = data
        else:
            return TaskDAG(tasks=[])

        tasks = []
        seen_ids: set[str] = set()
        for item in tasks_data:
            task_id = str(item.get("id", len(tasks) + 1))
            if task_id in seen_ids:
                task_id = f"{task_id}_{len(tasks)}"
            seen_ids.add(task_id)
            tasks.append(
                SubTask(
                    id=task_id,
                    description=item.get("description", ""),
                    dependencies=[str(d) for d in item.get("dependencies", [])],
                )
            )

        if not tasks:
            tasks = [SubTask(id="1", description="Complete the requirement", dependencies=[])]

        dag = TaskDAG(tasks=tasks)

        if dag.has_cycle():
            dag = self._break_cycles(dag)

        return dag

    def _break_cycles(self, dag: TaskDAG) -> TaskDAG:
        """Remove all dependencies to produce a clean DAG, as fallback."""
        for task in dag.tasks:
            task.dependencies = [d for d in task.dependencies if d in {t.id for t in dag.tasks}]
        return dag
