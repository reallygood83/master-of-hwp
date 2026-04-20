"""Parse natural-language edit requests into structured EditIntent objects.

Phase 0 ships a minimal rule-based parser so the full pipeline can be
tested end-to-end without an LLM. Phase 2 replaces the internals with
LLM-backed intent parsing while keeping this module's public signature
stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from master_of_hwp.core.document import HwpDocument


class EditAction(str, Enum):
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
