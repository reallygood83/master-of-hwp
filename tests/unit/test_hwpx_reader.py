"""Unit tests for the minimal HWPX ZIP reader."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from master_of_hwp.adapters.hwpx_reader import (
    HwpxFormatError,
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
def test_non_zip_raises_hwpx_format_error() -> None:
    with pytest.raises(HwpxFormatError, match="ZIP"):
        count_sections(b"NOT-A-ZIP-FILE" * 100)


@pytest.mark.unit
def test_extract_section_texts_empty_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        extract_section_texts(b"")


@pytest.mark.unit
def test_extract_section_paragraphs_empty_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        extract_section_paragraphs(b"")


@pytest.mark.unit
def test_extract_section_tables_empty_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        extract_section_tables(b"")


@pytest.mark.unit
def test_manifest_fallback_counts_section_refs() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "Contents/content.hpf",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/">'
                "<opf:manifest>"
                '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
                '<opf:item id="section1" href="Contents/section1.xml" media-type="application/xml"/>'
                "</opf:manifest>"
                "<opf:spine>"
                '<opf:itemref idref="section0" linear="yes"/>'
                '<opf:itemref idref="section1" linear="yes"/>'
                "</opf:spine>"
                "</opf:package>"
            ),
        )

    assert count_sections(buffer.getvalue()) == 2


@pytest.mark.unit
def test_extract_section_texts_manifest_fallback_preserves_order() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "Contents/content.hpf",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/">'
                "<opf:manifest>"
                '<opf:item id="section1" href="Contents/section1.xml" media-type="application/xml"/>'
                '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
                "</opf:manifest>"
                "<opf:spine>"
                '<opf:itemref idref="section0" linear="yes"/>'
                '<opf:itemref idref="section1" linear="yes"/>'
                "</opf:spine>"
                "</opf:package>"
            ),
        )
        archive.writestr(
            "Contents/section0.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
                'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'
                "<hp:p><hp:run><hp:t>first</hp:t><hp:t>-part</hp:t></hp:run></hp:p>"
                "<hp:p><hp:run><hp:t>line2</hp:t></hp:run></hp:p>"
                "</hs:sec>"
            ),
        )
        archive.writestr(
            "Contents/section1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
                'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'
                "<hp:p><hp:run><hp:t>second</hp:t></hp:run></hp:p>"
                "</hs:sec>"
            ),
        )

    assert extract_section_texts(buffer.getvalue()) == ["first-part\nline2", "second"]


@pytest.mark.unit
def test_extract_section_paragraphs_preserves_empty_paragraphs() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "Contents/section0.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
                'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'
                "<hp:p><hp:run><hp:t>first</hp:t></hp:run></hp:p>"
                "<hp:p><hp:run></hp:run></hp:p>"
                "<hp:p><hp:run><hp:t>third</hp:t></hp:run></hp:p>"
                "</hs:sec>"
            ),
        )

    assert extract_section_paragraphs(buffer.getvalue()) == [["first", "", "third"]]


@pytest.mark.unit
def test_real_sample_returns_positive_section_count(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
    if not sample.exists():
        pytest.skip("sample missing")

    section_count = count_sections(sample.read_bytes())

    assert section_count >= 1


@pytest.mark.unit
def test_extract_section_texts_real_sample_matches_section_count(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
    if not sample.exists():
        pytest.skip("sample missing")

    raw_bytes = sample.read_bytes()
    section_texts = extract_section_texts(raw_bytes)

    assert len(section_texts) == count_sections(raw_bytes)
    assert all(isinstance(text, str) for text in section_texts)
    assert any(text.strip() for text in section_texts)


@pytest.mark.unit
def test_extract_section_paragraphs_real_sample_matches_section_count(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
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
    assert ["\n".join(paragraphs) for paragraphs in section_paragraphs] == section_texts


@pytest.mark.unit
def test_extract_section_tables_real_sample_has_table_content(samples_dir: Path) -> None:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
    if not sample.exists():
        pytest.skip("sample missing")

    raw_bytes = sample.read_bytes()
    section_tables = extract_section_tables(raw_bytes)

    assert len(section_tables) == count_sections(raw_bytes)
    all_tables = [table for tables in section_tables for table in tables]
    assert all_tables
    assert all(len(table) >= 1 for table in all_tables)
    assert all(len(row) >= 1 for table in all_tables for row in table)
    assert all(
        all(isinstance(paragraph, str) for paragraph in cell)
        for table in all_tables
        for row in table
        for cell in row
    )
