"""Swappable extractors.

StubExtractor - offline keyword/regex stub, no dependencies, default for demo
and tests.
LocalLLMExtractor - uses a local Ollama model with JSON-constrained output.
"""

import json
import re


class StubExtractor:
    """Looks for `<field_key>: <value>` patterns in the message.

    Deliberately simple and offline -- this stub only needs to prove the
    extract -> apply_deltas -> missing() loop works end to end.
    """

    _PATTERN = re.compile(r"(\w+)\s*[:=]\s*(.+)")

    def extract(self, message: str, schema_text: str) -> dict[str, str]:
        known_keys = set(re.findall(r"^- (\w+)", schema_text, flags=re.MULTILINE))
        deltas: dict[str, str] = {}
        for line in message.splitlines():
            match = self._PATTERN.match(line.strip())
            if not match:
                continue
            key, value = match.group(1), match.group(2).strip()
            if key in known_keys:
                deltas[key] = value
        return deltas


class LocalLLMExtractor:
    """Extracts ontology field values via a local Ollama model.

    Prompts the model to return strict JSON mapping known field keys to
    values found in the message; anything else is dropped.
    """

    def __init__(self, model: str = "qwen3.5:9b", host: str = "http://localhost:11434"):
        self._model = model
        self._host = host

    def extract(self, message: str, schema_text: str) -> dict[str, str]:
        import requests

        prompt = (
            "You extract values for known fields from a user's natural-language message. "
            "The user will not use 'field: value' syntax -- infer values from ordinary "
            "conversational phrasing (e.g. 'I'm alex' implies name=Alex; "
            "'I don't feel good' implies emotion=bad/not good).\n"
            f"Known fields:\n{schema_text}\n\n"
            f"Message: {message}\n\n"
            "Return ONLY a JSON object mapping field keys to extracted values, using "
            "concise values (a name, a short emotion word/phrase, etc). "
            "Omit fields not mentioned or not inferable. No prose, no markdown."
        )
        response = requests.post(
            f"{self._host}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "think": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        raw = response.json().get("response", "{}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        known_keys = set(re.findall(r"^- (\w+)", schema_text, flags=re.MULTILINE))
        return {k: str(v) for k, v in parsed.items() if k in known_keys}
