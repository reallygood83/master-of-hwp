"""Round-trip fidelity harness for read and write path checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from master_of_hwp.core.document import SourceFormat


@dataclass(frozen=True)
class FidelityReport:
    """Summary of a fidelity check across read or write operations."""

    path: Path | None = None
    byte_equal: bool = False
    byte_diff_count: int = 0
    structural_equal: bool | None = None
    text_equal: bool | None = None
    score: float = 0.0
    sections_match: bool | None = None
    paragraphs_match: bool | None = None
    tables_match: bool | None = None
    edited_paragraph_applied: bool | None = None
    byte_size_delta: int = 0

    @property
    def passed(self) -> bool:
        """Whether the report satisfies its strongest populated invariants."""
        if self.byte_equal or self.structural_equal is True:
            return True
        checks = [
            check
            for check in (
                self.sections_match,
                self.paragraphs_match,
                self.tables_match,
                self.edited_paragraph_applied,
            )
            if check is not None
        ]
        return bool(checks) and all(checks)


def verify_identity_roundtrip(raw_bytes: bytes, source_format: SourceFormat) -> FidelityReport:
    """Re-parse a document with no edit and verify structural invariants."""
    adapter = _adapter_module(source_format)
    before_paragraphs = adapter.extract_section_paragraphs(raw_bytes)
    before_tables = adapter.extract_section_tables(raw_bytes)
    before_texts = adapter.extract_section_texts(raw_bytes)
    location = _first_paragraph_location(before_paragraphs)
    if location is None:
        edited_bytes = raw_bytes
    else:
        section_index, paragraph_index = location
        edited_bytes = adapter.replace_paragraph(
            raw_bytes,
            section_index,
            paragraph_index,
            before_paragraphs[section_index][paragraph_index],
        )
    after_paragraphs = adapter.extract_section_paragraphs(edited_bytes)
    after_tables = adapter.extract_section_tables(edited_bytes)
    after_texts = adapter.extract_section_texts(edited_bytes)
    sections_match = len(before_paragraphs) == len(after_paragraphs)
    paragraphs_match = before_paragraphs == after_paragraphs
    tables_match = _table_shape(before_tables) == _table_shape(after_tables)
    text_equal = before_texts == after_texts
    structural_equal = sections_match and paragraphs_match and tables_match
    byte_equal = raw_bytes == edited_bytes
    return FidelityReport(
        byte_equal=byte_equal,
        byte_diff_count=_count_byte_diffs(raw_bytes, edited_bytes),
        structural_equal=structural_equal,
        text_equal=text_equal,
        score=1.0 if byte_equal else 0.8 if structural_equal else 0.0,
        sections_match=sections_match,
        paragraphs_match=paragraphs_match,
        tables_match=tables_match,
        edited_paragraph_applied=True if location is None else None,
        byte_size_delta=len(edited_bytes) - len(raw_bytes),
    )


def verify_replace_roundtrip(
    raw_bytes: bytes,
    source_format: SourceFormat,
    section_index: int,
    paragraph_index: int,
    new_text: str,
) -> FidelityReport:
    """Apply replace_paragraph, re-parse, and verify invariants."""
    adapter = _adapter_module(source_format)
    before_paragraphs = adapter.extract_section_paragraphs(raw_bytes)
    before_tables = adapter.extract_section_tables(raw_bytes)
    edited_bytes = adapter.replace_paragraph(raw_bytes, section_index, paragraph_index, new_text)
    after_paragraphs = adapter.extract_section_paragraphs(edited_bytes)
    after_tables = adapter.extract_section_tables(edited_bytes)
    sections_match = len(before_paragraphs) == len(after_paragraphs)
    expected_paragraphs = _expected_paragraphs(
        before_paragraphs, section_index, paragraph_index, new_text
    )
    paragraphs_match = after_paragraphs == expected_paragraphs
    tables_match = _table_shape(before_tables) == _table_shape(after_tables)
    edited_paragraph_applied = (
        after_paragraphs[section_index][paragraph_index] == new_text
        if sections_match
        and 0 <= section_index < len(after_paragraphs)
        and 0 <= paragraph_index < len(after_paragraphs[section_index])
        else False
    )
    structural_equal = sections_match and paragraphs_match and tables_match
    return FidelityReport(
        byte_equal=raw_bytes == edited_bytes,
        byte_diff_count=_count_byte_diffs(raw_bytes, edited_bytes),
        structural_equal=structural_equal,
        text_equal=None,
        score=1.0 if structural_equal else 0.0,
        sections_match=sections_match,
        paragraphs_match=paragraphs_match,
        tables_match=tables_match,
        edited_paragraph_applied=edited_paragraph_applied,
        byte_size_delta=len(edited_bytes) - len(raw_bytes),
    )


def _adapter_module(source_format: SourceFormat) -> Any:
    if source_format is SourceFormat.HWP:
        from master_of_hwp.adapters import hwp5_reader

        return hwp5_reader
    if source_format is SourceFormat.HWPX:
        from master_of_hwp.adapters import hwpx_reader

        return hwpx_reader
    raise AssertionError(f"Unhandled source_format: {source_format!r}")


def _first_paragraph_location(section_paragraphs: list[list[str]]) -> tuple[int, int] | None:
    for section_index, paragraphs in enumerate(section_paragraphs):
        if paragraphs:
            return section_index, 0
    return None


def _expected_paragraphs(
    before_paragraphs: list[list[str]],
    section_index: int,
    paragraph_index: int,
    new_text: str,
) -> list[list[str]]:
    expected = [list(paragraphs) for paragraphs in before_paragraphs]
    expected[section_index][paragraph_index] = new_text
    return expected


def _table_shape(
    tables: list[list[list[list[list[str]]]]],
) -> list[list[tuple[int, tuple[int, ...]]]]:
    return [
        [(len(table), tuple(len(row) for row in table)) for table in section_tables]
        for section_tables in tables
    ]


def _count_byte_diffs(a: bytes, b: bytes) -> int:
    common = min(len(a), len(b))
    diffs = sum(1 for index in range(common) if a[index] != b[index])
    diffs += abs(len(a) - len(b))
    return diffs
