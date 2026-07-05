from __future__ import annotations

import asyncio
from typing import Callable

from codex.adapters.registry import AdapterRegistry
from codex.models import SubTask, SubtaskStatus, TaskDAG, SubtaskResult


class DAGExecutor:
    """Executes subtasks respecting DAG dependencies, with parallelism and retry."""

    def __init__(
        self,
        adapter_registry: AdapterRegistry,
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ):
        self._registry = adapter_registry
        self._max_retries = max_retries
        self._timeout = timeout_seconds

    async def execute(self, dag: TaskDAG, requirement: str) -> list[SubtaskResult]:
        """Execute all subtasks in topological order, parallelizing independent ones."""
        results: list[SubtaskResult] = []
        completed: dict[str, str] = {}  # task_id -> output text

        while not dag.all_done():
            ready = dag.get_ready_tasks()
            if not ready:
                # Shouldn't happen in a valid DAG, but handle dangling tasks
                pending = [t for t in dag.tasks if t.status == SubtaskStatus.PENDING]
                if pending:
                    ready = [pending[0]]
                else:
                    break

            # Execute ready tasks in parallel
            coros = [self._run_task(t, requirement, completed) for t in ready]
            batch_results = await asyncio.gather(*coros, return_exceptions=True)

            for task, result in zip(ready, batch_results):
                if isinstance(result, Exception):
                    task.status = SubtaskStatus.FAILED
                    task.error = str(result)
                    results.append(
                        SubtaskResult(
                            task_id=task.id,
                            description=task.description,
                            model=task.assigned_model or "unknown",
                            status=SubtaskStatus.FAILED,
                            error=str(result),
                        )
                    )
                else:
                    task.status = SubtaskStatus.COMPLETED
                    task.result = result.output
                    completed[task.id] = result.output or ""
                    results.append(result)

        return results

    async def _run_task(
        self,
        task: SubTask,
        requirement: str,
        completed: dict[str, str],
    ) -> SubtaskResult:
        task.status = SubtaskStatus.RUNNING
        model_name = task.assigned_model or "unknown"

        adapter = self._registry.get(model_name)

        # Build prompt with dependency context
        messages = self._build_messages(task, requirement, completed)

        last_error: str | None = None
        for attempt in range(self._max_retries):
            task.attempts = attempt + 1
            try:
                output = await asyncio.wait_for(
                    adapter.chat(messages, temperature=0.3),
                    timeout=self._timeout,
                )
                return SubtaskResult(
                    task_id=task.id,
                    description=task.description,
                    model=model_name,
                    status=SubtaskStatus.COMPLETED,
                    output=output,
                )
            except asyncio.TimeoutError:
                last_error = f"Timeout after {self._timeout}s"
            except Exception as e:
                last_error = str(e)

            if attempt < self._max_retries - 1:
                delays = [1, 2, 4]
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])

        return SubtaskResult(
            task_id=task.id,
            description=task.description,
            model=model_name,
            status=SubtaskStatus.FAILED,
            error=last_error or "Unknown error",
        )

    def _build_messages(
        self,
        task: SubTask,
        requirement: str,
        completed: dict[str, str],
    ) -> list[dict[str, str]]:
        system = (
            "You are an expert software engineer. Complete the assigned sub-task accurately. "
            "Output only the requested deliverable (code, explanation, etc.) with no extra commentary."
        )

        user_parts = [f"## Overall Requirement\n{requirement}\n"]
        user_parts.append(f"## Your Sub-Task\n{task.description}")

        if task.dependencies:
            deps_context = ["\n## Results from Dependent Tasks"]
            for dep_id in task.dependencies:
                if dep_id in completed:
                    deps_context.append(f"### Task {dep_id} Output:\n{completed[dep_id]}")
            user_parts.append("\n".join(deps_context))

        user_parts.append("\nProvide your output for this sub-task only.")

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(user_parts)},
        ]
