"""Swappable response generators.

EchoGenerator - deterministic offline stub, default for the demo and tests.
OpenRouterGenerator - targets a Claude model via OpenRouter's chat API.
LocalLLMGenerator - targets a local Ollama server via its native chat API.
"""

import os


def _build_messages(system: str, history: list[tuple[str, str]]) -> list[dict]:
    messages = [{"role": "system", "content": str(system)}]
    for user_msg, assistant_msg in history[:-1]:
        messages.append({"role": "user", "content": str(user_msg)})
        if assistant_msg:
            messages.append({"role": "assistant", "content": str(assistant_msg)})
    if history:
        messages.append({"role": "user", "content": str(history[-1][0])})
    return messages


class EchoGenerator:
    """Deterministic offline generator: echoes the system prompt's intent
    without calling any external service."""

    def generate(self, system: str, history: list[tuple[str, str]]) -> str:
        last_user = history[-1][0] if history else ""
        return f"[echo] Got it: '{last_user}'. {system.splitlines()[-1] if system else ''}".strip()


class OpenRouterGenerator:
    """Calls a Claude model through OpenRouter's chat completions API."""

    def __init__(self, model: str = "anthropic/claude-3.5-sonnet", api_key: str | None = None):
        self._model = model
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self._api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterGenerator")

    def generate(self, system: str, history: list[tuple[str, str]]) -> str:
        import requests

        messages = _build_messages(system, history)

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class LocalLLMGenerator:
    """Calls a local Ollama server's native /api/chat endpoint.

    Uses Ollama's native API (not the OpenAI-compatible /v1 one) because
    thinking models (e.g. qwen3.5) only reliably honor "think": false there --
    on the /v1 endpoint they can stall or return empty content.
    """

    def __init__(
        self,
        model: str = "qwen3.5:9b",
        base_url: str = "http://localhost:11434/v1",
    ):
        self._model = model
        self._host = base_url.removesuffix("/v1")

    def generate(self, system: str, history: list[tuple[str, str]]) -> str:
        import requests

        messages = _build_messages(system, history)
        response = requests.post(
            f"{self._host}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "stream": False,
                "think": False,
            },
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(
                f"Ollama /api/chat {response.status_code}: {response.text}"
            )
        return response.json()["message"]["content"]