"""OpenRouter (OpenAI-compatible) chat client.

A thin, defensive wrapper: it enforces a hard timeout, retries once on transient
failure, requests JSON output, and NEVER raises into the request path — every
failure mode returns ``None`` so the deterministic engine can take over.
"""

from __future__ import annotations

import json
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.logging import log_event

try:  # the SDK is optional at runtime (deterministic path needs no LLM)
    from openai import OpenAI
except Exception:  # pragma: no cover - import guard
    OpenAI = None  # type: ignore[assignment]


class LLMClient:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._client = None
        if OpenAI is not None and self.settings.llm_enabled:
            try:
                self._client = OpenAI(
                    api_key=self.settings.openrouter_api_key,
                    base_url=self.settings.openrouter_base_url,
                    timeout=self.settings.llm_timeout_seconds,
                    max_retries=0,  # we manage retries ourselves
                    default_headers={
                        "HTTP-Referer": self.settings.openrouter_referer,
                        "X-Title": self.settings.openrouter_title,
                    },
                )
            except Exception as exc:  # pragma: no cover - construction guard
                log_event("llm_init_failed", error=type(exc).__name__)
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete_json(self, system: str, user: str) -> Optional[dict]:
        """Return a parsed JSON object from the model, or ``None`` on any failure."""
        if self._client is None:
            return None

        attempts = max(1, self.settings.llm_max_retries + 1)
        for attempt in range(attempts):
            try:
                resp = self._client.chat.completions.create(
                    model=self.settings.model_name,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=900,
                    timeout=self.settings.llm_timeout_seconds,
                )
                content = (resp.choices[0].message.content or "").strip()
                if not content:
                    continue
                return _parse_json(content)
            except Exception as exc:
                log_event(
                    "llm_call_failed", attempt=attempt + 1, error=type(exc).__name__
                )
                continue
        return None


def _parse_json(content: str) -> Optional[dict]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Tolerate code-fenced or prefixed output by extracting the JSON object.
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
