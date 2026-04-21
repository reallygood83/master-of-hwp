"""LLM provider protocols and optional Anthropic implementation."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal provider interface used by the AI edit loop."""

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return raw text completion."""

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return structured JSON completion matching schema."""


class AnthropicProvider:
    """Anthropic Claude provider loaded lazily from the optional `ai` extra."""

    def __init__(self, model: str = "claude-opus-4-7", api_key: str | None = None) -> None:
        self.model = model
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Install master-of-hwp with the 'ai' extra to use AnthropicProvider."
            ) from exc
        self._client = anthropic.Anthropic(api_key=resolved_key)

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return raw text completion."""
        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [
            str(getattr(block, "text", ""))
            for block in getattr(message, "content", [])
            if getattr(block, "type", "") == "text"
        ]
        return "\n".join(part for part in parts if part).strip()

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return structured JSON completion matching schema."""
        del schema
        text = self.complete(
            system,
            f"{user}\n\nReturn only a JSON object. No markdown.",
            max_tokens=max_tokens,
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Anthropic response was not JSON: {text[:200]}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Anthropic response JSON was not an object.")
        return payload


class OpenAIProvider:
    """OpenAI provider loaded lazily from the optional `ai` extra.

    Suitable for the Codex CLI crowd (users who prefer OpenAI models).
    Uses the `openai` SDK and defaults to GPT-4o.
    """

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None) -> None:
        self.model = model
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Install master-of-hwp with the 'ai' extra + openai to use OpenAIProvider."
            ) from exc
        self._client = OpenAI(api_key=resolved_key)

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return raw text completion."""
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        return str(content).strip()

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return structured JSON completion matching schema."""
        del schema
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"{user}\n\nReturn only a JSON object."},
            ],
        )
        text = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI response was not JSON: {text[:200]}") from exc
        if not isinstance(payload, dict):
            raise ValueError("OpenAI response JSON was not an object.")
        return payload
