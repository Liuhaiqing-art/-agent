from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):
    """Abstract adapter for LLM providers."""

    def __init__(self, model_name: str, endpoint: str, api_key: str, max_tokens: int = 8192):
        self.model_name = model_name
        self.endpoint = endpoint
        self.api_key = api_key
        self.max_tokens = max_tokens

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> str:
        """Send chat request and return the response text."""
        ...
