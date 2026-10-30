"""Optional LLM abstraction. Disabled by default; nothing in the core workflow uses it.

Providers:
* ``none`` – disabled.
* ``ollama`` – ``POST {base_url}/api/chat`` (non-streaming).
* ``openai_compatible`` – ``POST {base_url}/chat/completions``; works with any server that
  implements the OpenAI chat completions format (e.g. Ollama's /v1, vLLM, LM Studio).
"""

from __future__ import annotations

from typing import Protocol

import httpx

from ..config import Settings

AI_LABEL = "AI-generated draft — verify every statement before use. Not saved automatically."


class LLMUnavailable(RuntimeError):
    pass


class LLMProvider(Protocol):
    name: str
    enabled: bool

    def complete(self, prompt: str, system: str = "") -> str: ...


class DisabledProvider:
    name = "none"
    enabled = False

    def complete(self, prompt: str, system: str = "") -> str:
        raise LLMUnavailable(
            "No LLM is configured. Set SEPB_LLM_PROVIDER, SEPB_LLM_BASE_URL and SEPB_LLM_MODEL "
            "to enable optional AI drafting. All core features work without it."
        )


class _HttpProvider:
    enabled = True

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 60.0,
                 transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self._client = httpx.Client(timeout=timeout, transport=transport)

    @staticmethod
    def _messages(prompt: str, system: str) -> list[dict[str, str]]:
        msgs = [{"role": "system", "content": system}] if system else []
        return msgs + [{"role": "user", "content": prompt}]

    def _post(self, url: str, payload: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            resp = self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailable(f"LLM request failed: {exc.__class__.__name__}") from exc


class OllamaProvider(_HttpProvider):
    name = "ollama"

    def complete(self, prompt: str, system: str = "") -> str:
        data = self._post(f"{self.base_url}/api/chat", {
            "model": self.model, "messages": self._messages(prompt, system), "stream": False,
        })
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMUnavailable("Unexpected response from Ollama") from exc


class OpenAICompatibleProvider(_HttpProvider):
    name = "openai_compatible"

    def complete(self, prompt: str, system: str = "") -> str:
        data = self._post(f"{self.base_url}/chat/completions", {
            "model": self.model, "messages": self._messages(prompt, system), "temperature": 0.2,
        })
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailable("Unexpected response from OpenAI-compatible endpoint") from exc


def build_provider(settings: Settings, transport: httpx.BaseTransport | None = None) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.llm_base_url, settings.llm_model, settings.llm_api_key,
                              settings.llm_timeout_seconds, transport)
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(settings.llm_base_url, settings.llm_model, settings.llm_api_key,
                                        settings.llm_timeout_seconds, transport)
    return DisabledProvider()
