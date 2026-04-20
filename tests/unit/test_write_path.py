"""Unit tests for write-path paragraph replacement and fidelity checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp.adapters.hwp5_reader import (
    Hwp5FormatError,
)
from master_of_hwp.adapters.hwp5_reader import (
    extract_section_paragraphs as extract_hwp5_section_paragraphs,
)
from master_of_hwp.adapters.hwp5_reader import (
    replace_paragraph as replace_hwp5_paragraph,
)
from master_of_hwp.adapters.hwpx_reader import (
    extract_section_paragraphs as extract_hwpx_section_paragraphs,
)
from master_of_hwp.adapters.hwpx_reader import (
    replace_paragraph as replace_hwpx_paragraph,
)
from master_of_hwp.core.document import SourceFormat
from master_of_hwp.fidelity import (
    FidelityReport,
    verify_identity_roundtrip,
    verify_replace_roundtrip,
)


def _first_nonempty_paragraph(section_paragraphs: list[list[str]]) -> tuple[int, int, str]:
    for section_index, paragraphs in enumerate(section_paragraphs):
        for paragraph_index, paragraph in enumerate(paragraphs):
            if paragraph:
                return section_index, paragraph_index, paragraph
    raise AssertionError("Expected at least one non-empty paragraph in sample.")


def _assert_other_paragraphs_unchanged(
    before: list[list[str]],
    after: list[list[str]],
    section_index: int,
    paragraph_index: int,
) -> None:
    assert len(before) == len(after)
    for current_section, (before_section, after_section) in enumerate(
        zip(before, after, strict=True)
    ):
        assert len(before_section) == len(after_section)
        for current_paragraph, (before_paragraph, after_paragraph) in enumerate(
            zip(before_section, after_section, strict=True)
        ):
            if current_section == section_index and current_paragraph == paragraph_index:
                continue
            assert after_paragraph == before_paragraph


@pytest.mark.unit
def test_hwpx_replace_paragraph_noop_same_length(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()
    section_paragraphs = extract_hwpx_section_paragraphs(raw_bytes)
    section_index, paragraph_index, paragraph = _first_nonempty_paragraph(section_paragraphs)

    report = verify_replace_roundtrip(
        raw_bytes,
        SourceFormat.HWPX,
        section_index,
        paragraph_index,
        paragraph,
    )

    assert isinstance(report, FidelityReport)
    assert report.sections_match
    assert report.paragraphs_match
    assert report.tables_match
    assert report.edited_paragraph_applied


@pytest.mark.unit
def test_hwpx_replace_paragraph_shorter(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()
    before = extract_hwpx_section_paragraphs(raw_bytes)
    section_index, paragraph_index, _paragraph = _first_nonempty_paragraph(before)

    edited = replace_hwpx_paragraph(raw_bytes, section_index, paragraph_index, "짧게")
    after = extract_hwpx_section_paragraphs(edited)

    assert after[section_index][paragraph_index] == "짧게"
    _assert_other_paragraphs_unchanged(before, after, section_index, paragraph_index)


@pytest.mark.unit
def test_hwpx_replace_paragraph_longer(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()
    before = extract_hwpx_section_paragraphs(raw_bytes)
    section_index, paragraph_index, _paragraph = _first_nonempty_paragraph(before)

    edited = replace_hwpx_paragraph(
        raw_bytes,
        section_index,
        paragraph_index,
        "조금 더 길어진 새 문장입니다.",
    )
    after = extract_hwpx_section_paragraphs(edited)

    assert after[section_index][paragraph_index] == "조금 더 길어진 새 문장입니다."
    _assert_other_paragraphs_unchanged(before, after, section_index, paragraph_index)


@pytest.mark.unit
def test_hwpx_replace_paragraph_out_of_range_raises(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()

    with pytest.raises(IndexError, match="section_index"):
        replace_hwpx_paragraph(raw_bytes, 999, 0, "변경")


@pytest.mark.unit
def test_hwp5_replace_paragraph_same_length_noop(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "re-mixed-0tr.hwp").read_bytes()
    section_paragraphs = extract_hwp5_section_paragraphs(raw_bytes)
    section_index, paragraph_index, paragraph = _first_nonempty_paragraph(section_paragraphs)

    edited = replace_hwp5_paragraph(raw_bytes, section_index, paragraph_index, paragraph)
    report = verify_identity_roundtrip(raw_bytes, SourceFormat.HWP)

    assert edited == raw_bytes
    assert isinstance(report, FidelityReport)
    assert report.sections_match
    assert report.paragraphs_match
    assert report.tables_match


@pytest.mark.unit
@pytest.mark.xfail(raises=Hwp5FormatError, reason="HWP5 resizing writer pending", strict=False)
def test_hwp5_replace_paragraph_different_length_xfails(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "re-mixed-0tr.hwp").read_bytes()
    replace_hwp5_paragraph(raw_bytes, 0, 0, "다른 길이의 문장")
