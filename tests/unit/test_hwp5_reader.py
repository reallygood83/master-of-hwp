"""Unit tests for the minimal HWP 5.0 binary reader."""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp.adapters.hwp5_reader import (
    Hwp5FormatError,
    count_sections,
    extract_section_paragraphs,
    extract_section_tables,
    extract_section_texts,
)


@pytest.mark.unit
def test_empty_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        count_sections(b"")


@pytest.mark.unit
def test_invalid_signature_raises_hwp5_format_error() -> None:
    with pytest.raises(Hwp5FormatError, match="compound file"):
        count_sections(b"NOT-A-HWP-FILE" * 100)


@pytest.mark.unit
def test_extract_section_texts_invalid_signature_raises_hwp5_format_error() -> None:
    with pytest.raises(Hwp5FormatError, match="compound file"):
        extract_section_texts(b"NOT-A-HWP-FILE" * 100)


@pytest.mark.unit
def test_extract_section_paragraphs_invalid_signature_raises_hwp5_format_error() -> None:
    with pytest.raises(Hwp5FormatError, match="compound file"):
        extract_section_paragraphs(b"NOT-A-HWP-FILE" * 100)


@pytest.mark.unit
def test_extract_section_tables_invalid_signature_raises_hwp5_format_error() -> None:
    with pytest.raises(Hwp5FormatError, match="compound file"):
        extract_section_tables(b"NOT-A-HWP-FILE" * 100)


@pytest.mark.unit
def test_real_sample_returns_positive_section_count(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "re-mixed-0tr.hwp"
    if not sample.exists():
        pytest.skip("sample missing")

    section_count = count_sections(sample.read_bytes())

    assert section_count >= 1


@pytest.mark.unit
def test_extract_section_texts_matches_section_count(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "re-mixed-0tr.hwp"
    if not sample.exists():
        pytest.skip("sample missing")

    raw_bytes = sample.read_bytes()
    section_texts = extract_section_texts(raw_bytes)

    assert len(section_texts) == count_sections(raw_bytes)
    assert all(isinstance(text, str) for text in section_texts)
    assert section_texts
    assert any(text.strip() for text in section_texts)


@pytest.mark.unit
def test_extract_section_paragraphs_matches_section_count(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "re-mixed-0tr.hwp"
    if not sample.exists():
        pytest.skip("sample missing")

    raw_bytes = sample.read_bytes()
    section_paragraphs = extract_section_paragraphs(raw_bytes)
    section_texts = extract_section_texts(raw_bytes)

    assert len(section_paragraphs) == count_sections(raw_bytes)
    assert all(isinstance(paragraphs, list) for paragraphs in section_paragraphs)
    assert all(
        all(isinstance(paragraph, str) for paragraph in paragraphs)
        for paragraphs in section_paragraphs
    )
    normalized_texts = [text.removesuffix("\r") for text in section_texts]
    joined_paragraphs = ["".join(paragraphs) for paragraphs in section_paragraphs]
    assert joined_paragraphs == normalized_texts


@pytest.mark.unit
def test_extract_section_tables_returns_expected_shape(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "re-mixed-0tr.hwp"
    if not sample.exists():
        pytest.skip("sample missing")

    raw_bytes = sample.read_bytes()
    section_tables = extract_section_tables(raw_bytes)

    assert len(section_tables) == count_sections(raw_bytes)
    assert all(isinstance(tables, list) for tables in section_tables)
    assert all(
        isinstance(row, list)
        and all(isinstance(cell, list) for cell in row)
        and all(all(isinstance(paragraph, str) for paragraph in cell) for cell in row)
        for tables in section_tables
        for table in tables
        for row in table
    )
