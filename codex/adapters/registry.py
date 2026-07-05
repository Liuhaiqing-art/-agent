from __future__ import annotations

from codex.adapters.base import BaseLLMAdapter
from codex.adapters.openai_compat import OpenAICompatAdapter
from codex.config import AppConfig, ModelConfig


class AdapterRegistry:
    """Creates and caches LLM adapters from config."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._adapters: dict[str, BaseLLMAdapter] = {}

    def get(self, model_name: str) -> BaseLLMAdapter:
        if model_name in self._adapters:
            return self._adapters[model_name]

        model = self._config.get_model(model_name)
        if model is None:
            raise ValueError(f"Unknown model: {model_name}")

        api_key = self._config.get_api_key(model)
        if not api_key:
            raise ValueError(
                f"API key not found for model {model_name}. "
                f"Set environment variable: {model.api_key_env}"
            )

        adapter = self._create_adapter(model, api_key)
        self._adapters[model_name] = adapter
        return adapter

    def _create_adapter(self, model: ModelConfig, api_key: str) -> BaseLLMAdapter:
        # All supported 国产 models use OpenAI-compatible API
        return OpenAICompatAdapter(
            model_name=model.name,
            endpoint=model.endpoint,
            api_key=api_key,
            max_tokens=model.max_tokens,
        )

    async def close_all(self) -> None:
        for adapter in self._adapters.values():
            if isinstance(adapter, OpenAICompatAdapter):
                await adapter.close()
        self._adapters.clear()
