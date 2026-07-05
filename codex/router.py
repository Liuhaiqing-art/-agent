from __future__ import annotations

import random

from codex.config import AppConfig, ModelConfig
from codex.models import TaskDAG, ComplexityLevel


class ModelRouter:
    """Assigns models to each subtask based on routing strategy."""

    def __init__(self, config: AppConfig):
        self._config = config

    def route(self, dag: TaskDAG, level: ComplexityLevel) -> TaskDAG:
        available = self._config.models
        if not available:
            return dag

        default_model = self._config.routing.default_executor or available[0].name

        for task in dag.tasks:
            if task.assigned_model:
                continue

            if level == ComplexityLevel.SIMPLE:
                task.assigned_model = self._pick_fastest(available, default_model)
            elif level == ComplexityLevel.MEDIUM:
                task.assigned_model = default_model
            else:
                # Complex: distribute across models for parallelism
                task.assigned_model = self._pick_round_robin(task.id, available, default_model)

        return dag

    def _pick_fastest(self, models: list[ModelConfig], fallback: str) -> str:
        fast = [m for m in models if "fast" in m.capabilities]
        if fast:
            return fast[0].name
        # Pick cheapest
        sorted_by_cost = sorted(models, key=lambda m: m.cost_per_1k_tokens)
        return sorted_by_cost[0].name if sorted_by_cost else fallback

    def _pick_round_robin(self, task_id: str, models: list[ModelConfig], fallback: str) -> str:
        idx = hash(task_id) % len(models)
        return models[idx].name

    def get_redundancy_model(self, primary_model: str) -> str | None:
        """For critical tasks, return a second model for redundancy."""
        if not self._config.routing.redundancy_on_critical:
            return None
        others = [m for m in self._config.models if m.name != primary_model]
        if not others:
            return None
        return random.choice(others).name
