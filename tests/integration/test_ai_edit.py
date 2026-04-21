"""Integration tests for natural-language edit loop."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from master_of_hwp import HwpDocument
from master_of_hwp.ai.intent import EditAction

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def hwpx_doc(samples_dir: Path) -> HwpDocument:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
    if not sample.exists():
        pytest.skip("HWPX sample missing")
    return HwpDocument.open(sample)


def test_ai_edit_rule_based_dry_run(hwpx_doc: HwpDocument) -> None:
    result = hwpx_doc.ai_edit("'윤호중 장관'을 '테스트 장관'으로 바꿔줘", dry_run=True)

    assert result.status == "refused"
    assert result.intent.action is EditAction.REPLACE_TEXT
    assert result.new_doc is hwpx_doc
    assert "Dry run" in result.message


def test_ai_edit_rule_based_applies_if_unique_match(hwpx_doc: HwpDocument) -> None:
    result = hwpx_doc.ai_edit("'윤호중 장관'을 '테스트 장관'으로 바꿔줘")

    assert result.status == "applied"
    assert result.locator is not None
    assert result.fidelity_report is not None
    assert result.fidelity_report.passed
    assert (
        result.new_doc.section_paragraphs[result.locator.section_index][
            result.locator.paragraph_index or 0
        ]
        == "테스트 장관"
    )


def test_ai_edit_confidence_threshold_refusal(hwpx_doc: HwpDocument) -> None:
    result = hwpx_doc.ai_edit(
        "'윤호중 장관'을 '테스트 장관'으로 바꿔줘",
        confidence_threshold=0.9,
    )

    assert result.status == "refused"
    assert "below threshold" in result.message
    assert result.new_doc is hwpx_doc


def test_ai_edit_rejects_unknown_intent(hwpx_doc: HwpDocument) -> None:
    result = hwpx_doc.ai_edit("오늘 날씨 어때?")

    assert result.status == "refused"
    assert result.intent.action is EditAction.UNKNOWN
    assert result.new_doc is hwpx_doc


def test_ai_edit_with_llm_integration(hwpx_doc: HwpDocument) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    from master_of_hwp.ai.providers import AnthropicProvider

    provider = AnthropicProvider()
    result = hwpx_doc.ai_edit(
        "문단에서 '윤호중 장관'을 찾아 '테스트 장관'으로 바꿔줘",
        provider=provider,
    )

    assert result.status in {"applied", "refused", "failed"}
