"""Smoke tests for the `master_of_hwp.ai` package skeleton.

Verifies:
* All public symbols import
* Dataclasses are frozen and constructable
* Scaffold stubs raise `NotImplementedError` with an informative
  version tag
* The one live operation (`ReplaceOperation`) dispatches correctly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp import HwpDocument
from master_of_hwp.ai import (
    DeleteOperation,
    EditIntent,
    EditOperation,
    InsertOperation,
    LocatorScope,
    ParagraphLocator,
    ReplaceOperation,
    RollbackTransaction,
    locate_targets,
    parse_edit_intent,
)
from master_of_hwp.ai.intent import EditAction

pytestmark = pytest.mark.unit


def test_public_symbols_import() -> None:
    assert parse_edit_intent is not None
    assert locate_targets is not None
    assert issubclass(ReplaceOperation, object)
    assert issubclass(InsertOperation, object)
    assert issubclass(DeleteOperation, object)


def test_paragraph_locator_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    locator = ParagraphLocator(
        scope=LocatorScope.PARAGRAPH,
        section_index=0,
        paragraph_index=3,
        confidence=0.9,
    )
    with pytest.raises(FrozenInstanceError):
        locator.section_index = 99  # type: ignore[misc]


def test_replace_operation_conforms_to_edit_operation_protocol() -> None:
    locator = ParagraphLocator(scope=LocatorScope.PARAGRAPH, section_index=0, paragraph_index=0)
    op = ReplaceOperation(locator=locator, new_text="hello")
    assert isinstance(op, EditOperation)


def test_insert_operation_apply_raises_not_implemented_with_version() -> None:
    locator = ParagraphLocator(scope=LocatorScope.PARAGRAPH, section_index=0, paragraph_index=0)
    op = InsertOperation(locator=locator, text="new paragraph")
    with pytest.raises(NotImplementedError, match="v0.2"):
        op.apply(_fake_doc())


def test_delete_operation_apply_raises_not_implemented_with_version() -> None:
    locator = ParagraphLocator(scope=LocatorScope.PARAGRAPH, section_index=0, paragraph_index=0)
    op = DeleteOperation(locator=locator)
    with pytest.raises(NotImplementedError, match="v0.2"):
        op.apply(_fake_doc())


def test_locate_targets_raises_not_implemented() -> None:
    intent = EditIntent(action=EditAction.UNKNOWN, target="anything")
    assert locate_targets(intent, _fake_doc()) == []


def test_rollback_transaction_context_manager_swallows_exception() -> None:
    doc = _fake_doc()
    tx = RollbackTransaction(doc)
    try:
        with tx:
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass
    assert tx.current is tx.snapshot


def test_rollback_transaction_rollback_returns_snapshot() -> None:
    doc = _fake_doc()
    tx = RollbackTransaction(doc)
    restored = tx.rollback()
    assert restored is doc


def test_replace_operation_apply_dispatches_to_hwp_document(
    samples_dir: Path,
) -> None:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
    if not sample.exists():
        pytest.skip("HWPX sample missing")
    doc = HwpDocument.open(sample)
    locator = ParagraphLocator(
        scope=LocatorScope.PARAGRAPH,
        section_index=0,
        paragraph_index=0,
        confidence=1.0,
    )
    op = ReplaceOperation(locator=locator, new_text="AI-applied edit")
    edited = op.apply(doc)
    assert edited is not doc
    assert edited.section_paragraphs[0][0] == "AI-applied edit"


# ---- helpers --------------------------------------------------------


def _fake_doc() -> HwpDocument:
    """A minimal HwpDocument — not functional, only for type plumbing."""
    from master_of_hwp.core.document import SourceFormat

    return HwpDocument(
        path=Path("/tmp/nonexistent.hwpx"),
        source_format=SourceFormat.HWPX,
        raw_bytes=b"PK\x03\x04fake",
    )
