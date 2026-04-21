"""Parse natural-language edit requests into structured EditIntent objects.

Phase 0 ships a minimal rule-based parser so the full pipeline can be
tested end-to-end without an LLM. Phase 2 replaces the internals with
LLM-backed intent parsing while keeping this module's public signature
stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from master_of_hwp.core.document import HwpDocument


class EditAction(StrEnum):
    """High-level action categories the agent can request."""

    REPLACE_TEXT = "replace_text"
    INSERT_PARAGRAPH = "insert_paragraph"
    DELETE_RANGE = "delete_range"
    CREATE_TABLE = "create_table"
    UPDATE_TABLE_CELL = "update_table_cell"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EditIntent:
    """A structured description of a requested edit.

    Attributes:
        action: The action category.
        target: A human-readable description of what to edit (e.g.,
            "3페이지 표의 2열").
        parameters: Action-specific key/value parameters.
        confidence: Parser's confidence in the interpretation (0.0–1.0).
        raw_request: The original natural-language request, preserved
            for audit / debugging.
    """

    action: EditAction
    target: str
    parameters: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    raw_request: str = ""


INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "replace_text",
                "insert_paragraph",
                "delete_range",
                "update_table_cell",
                "unknown",
            ],
        },
        "target_description": {"type": "string"},
        "parameters": {
            "type": "object",
            "properties": {
                "find": {"type": "string"},
                "replace_with": {"type": "string"},
            },
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["action", "target_description", "confidence"],
}


def parse_edit_intent(request: str, doc: HwpDocument) -> EditIntent:
    """Translate a natural-language edit request into an EditIntent.

    Phase 0: rule-based stub. Returns UNKNOWN with confidence 0.0 for
    everything it cannot recognize. This is intentional — the stub
    exposes the full pipeline wiring while leaving actual intelligence
    to Phase 2.

    Args:
        request: A Korean or English natural-language edit instruction.
        doc: The document the edit will apply to. Used in future
            implementations for context-aware disambiguation.

    Returns:
        An EditIntent describing the requested action. Callers must
        check .confidence and .action before executing.
    """
    del doc  # Unused in Phase 0 stub; reserved for context-aware parsing.

    text = request.strip()
    lowered = text.lower()

    if not text:
        return EditIntent(
            action=EditAction.UNKNOWN,
            target="",
            raw_request=request,
        )

    if "셀" in text or "cell" in lowered:
        return EditIntent(
            action=EditAction.UPDATE_TABLE_CELL,
            target=text,
            confidence=0.3,
            raw_request=request,
        )

    if "표" in text or "table" in lowered:
        action = (
            EditAction.CREATE_TABLE
            if ("만들" in text or "create" in lowered)
            else EditAction.UPDATE_TABLE_CELL
        )
        return EditIntent(
            action=action,
            target=text,
            confidence=0.3,
            raw_request=request,
        )

    if "삭제" in text or "delete" in lowered or "지워" in text:
        return EditIntent(
            action=EditAction.DELETE_RANGE,
            target=text,
            confidence=0.3,
            raw_request=request,
        )

    if "추가" in text or "insert" in lowered or "넣어" in text:
        return EditIntent(
            action=EditAction.INSERT_PARAGRAPH,
            target=text,
            confidence=0.3,
            raw_request=request,
        )

    replacement = _parse_replacement_parameters(text)
    if replacement is not None:
        find_text, replace_with = replacement
        return EditIntent(
            action=EditAction.REPLACE_TEXT,
            target=find_text,
            parameters={"find": find_text, "replace_with": replace_with},
            confidence=0.6,
            raw_request=request,
        )

    if "바꿔" in text or "replace" in lowered or "변경" in text:
        return EditIntent(
            action=EditAction.REPLACE_TEXT,
            target=text,
            confidence=0.3,
            raw_request=request,
        )

    return EditIntent(
        action=EditAction.UNKNOWN,
        target=text,
        confidence=0.0,
        raw_request=request,
    )


def parse_intent_llm(request: str, doc: HwpDocument, provider: object) -> EditIntent:
    """Parse an edit request with an LLM provider, falling back to rules."""
    from master_of_hwp.ai.providers import LLMProvider

    typed_provider = provider
    if not isinstance(typed_provider, LLMProvider):
        return parse_edit_intent(request, doc)
    system = (
        "You parse natural-language document edit requests. "
        "Return JSON with action, target_description, parameters, confidence."
    )
    user = f"Request: {request}\nDocument summary: {doc.summary()}"
    try:
        payload = typed_provider.complete_json(system, user, INTENT_SCHEMA)
        action = EditAction(str(payload.get("action", EditAction.UNKNOWN.value)))
        parameters = payload.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}
        target = str(payload.get("target_description", ""))
        confidence = float(payload.get("confidence", 0.0))
    except Exception:
        return parse_edit_intent(request, doc)
    return EditIntent(
        action=action,
        target=target,
        parameters={str(key): str(value) for key, value in parameters.items()},
        confidence=max(0.0, min(confidence, 1.0)),
        raw_request=request,
    )


def _parse_replacement_parameters(text: str) -> tuple[str, str] | None:
    quoted = _quoted_segments(text)
    if len(quoted) >= 2 and any(marker in text for marker in ("바꿔", "변경", "replace")):
        return quoted[0], quoted[1]
    lowered = text.lower()
    if "replace " in lowered and " with " in lowered:
        before, _sep, after = text.partition(" with ")
        find_text = before.replace("replace", "", 1).strip(" :\"'")
        replace_with = after.strip(" :\"'")
        if find_text and replace_with:
            return find_text, replace_with
    return None


def _quoted_segments(text: str) -> list[str]:
    segments: list[str] = []
    quote_pairs = [("'", "'"), ('"', '"'), ("‘", "’"), ("“", "”")]
    for open_quote, close_quote in quote_pairs:
        start = 0
        while True:
            left = text.find(open_quote, start)
            if left < 0:
                break
            right = text.find(close_quote, left + 1)
            if right < 0:
                break
            segment = text[left + 1 : right]
            if segment:
                segments.append(segment)
            start = right + 1
    return segments
