"""AI backend abstraction.

Two wire protocols cover all supported backends:

* **Ollama** native ``/api/chat``.
* **OpenAI-compatible** ``/v1/chat/completions`` — used for LM Studio
  (default ``http://localhost:1234/v1``), OpenAI itself, OpenRouter
  (``https://openrouter.ai/api/v1``), vLLM, llama.cpp server, LocalAI, etc.

Plugins can register additional backends through the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from zen.core.exceptions import AIUnavailableError


@dataclass(slots=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class ChatOptions:
    model: str
    temperature: float = 0.3
    max_tokens: int = 1024
    timeout_seconds: float = 120.0


class AIBackend(Protocol):
    name: str

    async def chat(self, messages: list[ChatMessage], options: ChatOptions) -> str: ...
    async def list_models(self) -> list[str]: ...
    async def ping(self) -> bool: ...


class OllamaBackend:
    name = "ollama"

    def __init__(self, base_url: str = "", api_key: str = "") -> None:
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.api_key = api_key  # unused; Ollama has no auth by default

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def chat(self, messages: list[ChatMessage], options: ChatOptions) -> str:
        payload = {
            "model": options.model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": options.temperature,
                "num_predict": options.max_tokens,
            },
        }
        try:
            async with self._client(options.timeout_seconds) as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"Ollama request failed: {exc}") from exc
        content = (data.get("message") or {}).get("content", "")
        if not content:
            raise AIUnavailableError("Ollama returned an empty response.")
        return content

    async def list_models(self) -> list[str]:
        try:
            async with self._client(10.0) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"Ollama request failed: {exc}") from exc
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    async def ping(self) -> bool:
        try:
            async with self._client(5.0) as client:
                response = await client.get("/api/version")
                return response.status_code == 200
        except httpx.HTTPError:
            return False


class OpenAICompatBackend:
    """Speaks /v1/chat/completions. Covers OpenAI, OpenRouter, LM Studio, vLLM."""

    name = "openai"

    def __init__(self, base_url: str = "", api_key: str = "") -> None:
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(self, messages: list[ChatMessage], options: ChatOptions) -> str:
        payload = {
            "model": options.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=options.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"AI request failed: {exc}") from exc
        choices = data.get("choices") or []
        if not choices:
            raise AIUnavailableError("AI backend returned no choices.")
        content = (choices[0].get("message") or {}).get("content", "")
        if not content:
            raise AIUnavailableError("AI backend returned an empty response.")
        return content

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"AI request failed: {exc}") from exc
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]

    async def ping(self) -> bool:
        try:
            await self.list_models()
            return True
        except AIUnavailableError:
            return False


_BACKEND_FACTORIES: dict[str, type] = {}


def register_backend(name: str, factory: type, *, replace: bool = False) -> None:
    if name in _BACKEND_FACTORIES and not replace:
        raise ValueError(f"AI backend '{name}' is already registered.")
    _BACKEND_FACTORIES[name] = factory


def build_backend(name: str, base_url: str = "", api_key: str = "") -> AIBackend:
    if name == "ollama":
        return OllamaBackend(base_url=base_url, api_key=api_key)
    if name == "lmstudio":
        return OpenAICompatBackend(
            base_url=base_url or "http://localhost:1234/v1", api_key=api_key
        )
    if name == "openrouter":
        return OpenAICompatBackend(
            base_url=base_url or "https://openrouter.ai/api/v1", api_key=api_key
        )
    if name == "openai":
        return OpenAICompatBackend(base_url=base_url, api_key=api_key)
    factory = _BACKEND_FACTORIES.get(name)
    if factory is None:
        raise AIUnavailableError(f"Unknown AI backend: {name}")
    return factory(base_url=base_url, api_key=api_key)
