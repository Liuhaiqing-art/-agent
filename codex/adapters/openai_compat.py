from __future__ import annotations

import json

import httpx

from codex.adapters.base import BaseLLMAdapter


class OpenAICompatAdapter(BaseLLMAdapter):
    """Adapter for any OpenAI-compatible API (DeepSeek, Qwen, 文心一言, etc.)."""

    def __init__(self, model_name: str, endpoint: str, api_key: str, max_tokens: int = 8192):
        super().__init__(model_name, endpoint, api_key, max_tokens)
        endpoint = endpoint.rstrip("/")
        self._chat_url = f"{endpoint}/chat/completions"
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> str:
        payload: dict = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        for attempt in range(3):
            try:
                resp = await self.client.post(self._chat_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError) as e:
                if attempt == 2:
                    raise
                await _backoff_sleep(attempt)
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                raise ValueError(f"Unexpected API response format: {e}") from e

        raise RuntimeError("unreachable")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


async def _backoff_sleep(attempt: int) -> None:
    import asyncio

    delays = [1, 2, 4]
    await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
