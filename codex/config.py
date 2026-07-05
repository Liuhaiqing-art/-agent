from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class ModelConfig(BaseModel):
    name: str
    provider: str
    endpoint: str
    api_key_env: str = ""
    api_key: str = ""
    capabilities: list[str] = []
    cost_per_1k_tokens: float = 0.0
    max_tokens: int = 8192


class RoutingConfig(BaseModel):
    analyzer_model: str = ""
    decomposer_model: str = ""
    default_executor: str = ""
    parallel_threshold: int = 3
    redundancy_on_critical: bool = False
    max_retries: int = 3
    timeout_seconds: int = 300


class AppConfig(BaseModel):
    models: list[ModelConfig] = []
    routing: RoutingConfig = RoutingConfig()

    def get_model(self, name: str) -> Optional[ModelConfig]:
        for m in self.models:
            if m.name == name:
                return m
        return None

    def get_api_key(self, model: ModelConfig) -> Optional[str]:
        if model.api_key:
            return model.api_key
        if model.api_key_env:
            return os.environ.get(model.api_key_env)
        return None


def load_config(path: str = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    models = [ModelConfig(**m) for m in raw.get("models", [])]
    routing = RoutingConfig(**raw.get("routing", {}))
    return AppConfig(models=models, routing=routing)
