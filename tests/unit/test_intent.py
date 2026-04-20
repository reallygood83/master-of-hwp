"""Unit tests for master_of_hwp.ai.intent."""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp import HwpDocument
from master_of_hwp.ai import EditIntent, parse_edit_intent
from master_of_hwp.ai.intent import EditAction


@pytest.fixture
def doc(tmp_hwpx: Path) -> HwpDocument:
    return HwpDocument.open(tmp_hwpx)


@pytest.mark.unit
class TestParseEditIntent:
    def test_empty_request_returns_unknown(self, doc: HwpDocument) -> None:
        intent = parse_edit_intent("   ", doc)
        assert intent.action is EditAction.UNKNOWN
        assert intent.confidence == 0.0

    @pytest.mark.parametrize(
        ("utterance", "expected_action"),
        [
            ("3번째 단락을 삭제해줘", EditAction.DELETE_RANGE),
            ("please delete the first paragraph", EditAction.DELETE_RANGE),
            ("여기 표를 만들어줘", EditAction.CREATE_TABLE),
            ("create a table with 3 rows", EditAction.CREATE_TABLE),
            ("이 셀 내용을 바꿔줘", EditAction.UPDATE_TABLE_CELL),
            ("새 문단을 추가해줘", EditAction.INSERT_PARAGRAPH),
            ("제목을 '안내'로 변경", EditAction.REPLACE_TEXT),
        ],
    )
    def test_recognizes_common_actions(
        self, utterance: str, expected_action: EditAction, doc: HwpDocument
    ) -> None:
        intent = parse_edit_intent(utterance, doc)
        assert intent.action is expected_action
        assert intent.confidence > 0.0
        assert intent.raw_request == utterance

    def test_unrecognized_returns_unknown(self, doc: HwpDocument) -> None:
        intent = parse_edit_intent("오늘 날씨 어때?", doc)
        assert intent.action is EditAction.UNKNOWN

    def test_intent_is_frozen(self, doc: HwpDocument) -> None:
        intent = parse_edit_intent("삭제", doc)
        assert isinstance(intent, EditIntent)
        with pytest.raises((AttributeError, TypeError)):
            intent.confidence = 0.99  # type: ignore[misc]
