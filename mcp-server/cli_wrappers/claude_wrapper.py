from __future__ import annotations

import json
import subprocess
from typing import TypedDict


class ClaudeRunResult(TypedDict):
    ok: bool
    raw_text: str
    structured: dict[str, object]


class ClaudeWrapperError(Exception):
    """Raised when Claude CLI execution fails or returns invalid output."""


def run_claude_json(prompt: str) -> ClaudeRunResult:
    command = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        prompt,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    payload = _parse_outer_payload(result.stdout)
    if result.returncode != 0:
        if payload is not None:
            error_message = str(payload.get("result") or payload.get("message") or "claude cli failed")
            raise ClaudeWrapperError(error_message)
        stderr = result.stderr.strip() or "no stderr provided"
        raise ClaudeWrapperError(f"claude cli failed: {stderr}")

    if payload is None:
        stdout = result.stdout.strip()
        if not stdout:
            raise ClaudeWrapperError("claude cli returned empty output")
        raise ClaudeWrapperError("claude cli returned invalid JSON output")

    raw_text = str(payload.get("result", "")).strip()
    if not raw_text:
        raise ClaudeWrapperError("claude cli JSON did not include a result field")

    try:
        structured = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ClaudeWrapperError(
            f"claude result was not valid JSON as instructed: {exc}; raw={raw_text[:300]}"
        ) from exc

    if not isinstance(structured, dict):
        raise ClaudeWrapperError("claude result JSON was not an object")

    return {
        "ok": True,
        "raw_text": raw_text,
        "structured": structured,
    }


def _parse_outer_payload(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
