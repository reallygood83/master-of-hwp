"""Resolve an `EditIntent` to concrete document coordinates.

Given a parsed intent (which only knows *what* the user said) and a
document, the locator decides *where* in the document the edit should
apply. Phase 2 will replace the stub with a content-aware targeter
that combines `HwpDocument.find_paragraphs` with LLM re-ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from master_of_hwp.ai.intent import EditAction, EditIntent
from master_of_hwp.core.document import HwpDocument


class LocatorScope(StrEnum):
    """Where in the document a located target lives."""

    PARAGRAPH = "paragraph"
    TABLE_CELL = "table_cell"
    SECTION = "section"


@dataclass(frozen=True)
class ParagraphLocator:
    """Structured pointer to a paragraph or cell inside a document.

    Attributes:
        scope: Whether the target is a paragraph, a table cell, or an
            entire section.
        section_index: Zero-based section index.
        paragraph_index: Zero-based paragraph index within the section;
            `None` when `scope` is `SECTION`.
        table_index: Zero-based table index, when `scope` is `TABLE_CELL`.
        row_index: Zero-based row index, when `scope` is `TABLE_CELL`.
        cell_index: Zero-based cell index, when `scope` is `TABLE_CELL`.
        confidence: Locator's confidence that this is the intended
            target (0.0–1.0). Callers should refuse to execute below a
            configured threshold.
    """

    scope: LocatorScope
    section_index: int
    paragraph_index: int | None = None
    table_index: int | None = None
    row_index: int | None = None
    cell_index: int | None = None
    confidence: float = 0.0


def locate_targets(
    intent: EditIntent,
    doc: HwpDocument,
    provider: object | None = None,
) -> list[ParagraphLocator]:
    """Resolve an `EditIntent` into candidate target locations.

    Args:
        intent: A parsed `EditIntent`.
        doc: The document to locate targets within.
        provider: Optional LLM provider for future disambiguation.

    Returns:
        A list of `ParagraphLocator` candidates sorted by confidence
        (highest first). An empty list indicates no match above the
        implementation-defined confidence floor.

    """
    if intent.action is not EditAction.REPLACE_TEXT:
        return []
    needle = intent.parameters.get("find") or intent.target
    if not needle:
        return []
    hits = doc.find_paragraphs(needle)
    if not hits:
        return []
    if len(hits) == 1:
        section_index, paragraph_index, _text = hits[0]
        return [
            ParagraphLocator(
                scope=LocatorScope.PARAGRAPH,
                section_index=section_index,
                paragraph_index=paragraph_index,
                confidence=1.0,
            )
        ]
    if provider is not None:
        reranked = _rerank_with_provider(intent, hits, provider)
        if reranked is not None:
            return [reranked]
    section_index, paragraph_index, _text = hits[0]
    return [
        ParagraphLocator(
            scope=LocatorScope.PARAGRAPH,
            section_index=section_index,
            paragraph_index=paragraph_index,
            confidence=0.5,
        )
    ]


def _rerank_with_provider(
    intent: EditIntent,
    hits: list[tuple[int, int, str]],
    provider: object,
) -> ParagraphLocator | None:
    from master_of_hwp.ai.providers import LLMProvider

    if not isinstance(provider, LLMProvider):
        return None
    candidates = [
        {"section": section, "paragraph": paragraph, "text": text}
        for section, paragraph, text in hits
    ]
    schema = {
        "type": "object",
        "properties": {
            "section": {"type": "integer"},
            "paragraph": {"type": "integer"},
            "confidence": {"type": "number"},
        },
        "required": ["section", "paragraph", "confidence"],
    }
    try:
        payload = provider.complete_json(
            "Choose the best paragraph candidate for this edit.",
            f"Intent: {intent}\nCandidates: {candidates}",
            schema,
        )
        section_index = int(payload["section"])
        paragraph_index = int(payload["paragraph"])
        confidence = float(payload.get("confidence", 0.7))
    except Exception:
        return None
    for section, paragraph, _text in hits:
        if section == section_index and paragraph == paragraph_index:
            return ParagraphLocator(
                scope=LocatorScope.PARAGRAPH,
                section_index=section,
                paragraph_index=paragraph,
                confidence=max(0.0, min(confidence, 1.0)),
            )
    return None
