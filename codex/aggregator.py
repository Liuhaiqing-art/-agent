from __future__ import annotations

from codex.adapters.base import BaseLLMAdapter
from codex.models import SubtaskResult, AggregatedResult, SubtaskStatus

AGGREGATOR_SYSTEM_PROMPT = """\
You are a result aggregation engine. You receive multiple sub-task outputs from different LLMs and must synthesize them into a single coherent response.

Rules:
1. Combine outputs in logical order (follow the sub-task sequence)
2. Remove redundant information across outputs
3. Resolve any contradictions between outputs (if outputs differ, choose the most correct/reasonable one or note the discrepancy)
4. Format the final output clearly with appropriate headings/code blocks
5. Preserve all working code and important details from each output
6. If any sub-task failed, note what was not completed

Return ONLY a JSON object:
{
  "summary": "brief summary of what was accomplished",
  "final_output": "the complete synthesized output"
}
"""


class ResultAggregator:
    """Merges multiple sub-task results into a coherent final output."""

    def __init__(self, adapter: BaseLLMAdapter):
        self._adapter = adapter

    async def aggregate(
        self,
        requirement: str,
        subtask_results: list[SubtaskResult],
    ) -> AggregatedResult:
        if not subtask_results:
            return AggregatedResult(
                summary="No results produced",
                subtask_results=[],
                final_output="",
            )

        # If only one subtask, no aggregation needed
        if len(subtask_results) == 1:
            r = subtask_results[0]
            return AggregatedResult(
                summary=r.output or "",
                subtask_results=subtask_results,
                final_output=r.output or "",
            )

        successful = [r for r in subtask_results if r.status == SubtaskStatus.COMPLETED]
        if not successful:
            errors = "\n".join(f"- {r.task_id}: {r.error}" for r in subtask_results)
            return AggregatedResult(
                summary="All sub-tasks failed",
                subtask_results=subtask_results,
                final_output=f"All sub-tasks failed:\n{errors}",
            )

        # Use LLM to synthesize results
        parts = ["## Original Requirement\n" + requirement + "\n"]
        parts.append("## Sub-Task Results (in order)\n")
        for i, r in enumerate(subtask_results):
            status = "COMPLETED" if r.status == SubtaskStatus.COMPLETED else f"FAILED: {r.error}"
            parts.append(f"### {i + 1}. [{status}] {r.description} (model: {r.model})")
            if r.output:
                parts.append(r.output)
            parts.append("")

        user_message = "\n".join(parts)

        messages = [
            {"role": "system", "content": AGGREGATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            import json

            raw = await self._adapter.chat(messages, temperature=0.3, response_format={"type": "json_object"})
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
                if raw.endswith("```"):
                    raw = raw[:-3].strip()
            data = json.loads(raw)
            summary = data.get("summary", "")
            final_output = data.get("final_output", "")
        except Exception:
            # Fallback: concatenate outputs
            summary = f"Synthesized {len(successful)}/{len(subtask_results)} sub-task results"
            final_output = "\n\n---\n\n".join(r.output or "" for r in subtask_results if r.output)

        return AggregatedResult(
            summary=summary,
            subtask_results=subtask_results,
            final_output=final_output,
        )
