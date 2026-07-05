from __future__ import annotations

import json

from codex.adapters.base import BaseLLMAdapter
from codex.models import ComplexityAssessment, ComplexityLevel, TaskType

ANALYZER_SYSTEM_PROMPT = """\
You are a task complexity analyzer. Given a user's requirement, you must classify it and return ONLY a JSON object with no other text.

Analyze along these dimensions:
1. How many distinct sub-tasks does this requirement imply? (1 = single step, 2-3 = moderate, 4+ = complex)
2. Are there clear dependencies between sub-parts? (sequential steps that depend on each other)
3. How broad is the domain knowledge needed? (single concept vs. multiple domains)
4. Is the requirement ambiguous or does it need clarification?

Output format:
{
  "level": "simple" | "medium" | "complex",
  "task_type": "code_generation" | "bug_fix" | "refactor" | "analysis" | "question" | "other",
  "estimated_subtasks": <integer>,
  "reasoning": "<brief explanation in the user's language>"
}

Classification rules:
- "simple": single clear task, no dependencies, one domain (e.g., "write a function to sort a list", "what does git status do")
- "medium": 2-3 connected tasks, some dependencies, maybe 2 domains (e.g., "add error handling to this module", "write a CRUD API for users")
- "complex": 4+ tasks, intricate dependencies, multiple domains, or ambiguous (e.g., "build a microservice with auth, rate limiting, and logging", "refactor the entire auth system")

task_type mapping:
- "code_generation": writing new code, creating features/modules
- "bug_fix": debugging, fixing issues
- "refactor": restructuring existing code
- "analysis": code review, performance analysis, security audit
- "question": asking a technical question
- "other": none of the above
"""


class ComplexityAnalyzer:
    """Uses an LLM to analyze how complex a user requirement is."""

    def __init__(self, adapter: BaseLLMAdapter):
        self._adapter = adapter

    async def analyze(self, requirement: str, context: str = "") -> ComplexityAssessment:
        user_message = f"Requirement:\n{requirement}"
        if context:
            user_message += f"\n\nAdditional context:\n{context}"

        messages = [
            {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw = await self._adapter.chat(messages, temperature=0.1, response_format={"type": "json_object"})
        return self._parse(raw)

    def _parse(self, raw: str) -> ComplexityAssessment:
        raw = raw.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return ComplexityAssessment(
                level=ComplexityLevel.MEDIUM,
                task_type=TaskType.OTHER,
                estimated_subtasks=1,
                reasoning="Failed to parse analyzer response",
            )

        level = data.get("level", "medium")
        if level not in ("simple", "medium", "complex"):
            level = "medium"

        task_type = data.get("task_type", "other")
        valid_types = {"code_generation", "bug_fix", "refactor", "analysis", "question", "other"}
        if task_type not in valid_types:
            task_type = "other"

        return ComplexityAssessment(
            level=ComplexityLevel(level),
            task_type=TaskType(task_type),
            estimated_subtasks=max(1, int(data.get("estimated_subtasks", 1))),
            reasoning=data.get("reasoning", ""),
        )
