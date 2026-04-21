"""Unit tests for HWPX table cell paragraph replacement."""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp.adapters.hwpx_reader import (
    extract_section_tables,
    replace_table_cell_paragraph,
)


def _first_nonempty_cell_paragraph(
    section_tables: list[list[list[list[list[str]]]]],
) -> tuple[int, int, int, int, int, str]:
    for section_index, tables in enumerate(section_tables):
        for table_index, table in enumerate(tables):
            for row_index, row in enumerate(table):
                for cell_index, cell in enumerate(row):
                    for paragraph_index, paragraph in enumerate(cell):
                        if paragraph:
                            return (
                                section_index,
                                table_index,
                                row_index,
                                cell_index,
                                paragraph_index,
                                paragraph,
                            )
    raise AssertionError("Expected sample to contain a non-empty table cell paragraph.")


def _assert_other_cells_unchanged(
    before: list[list[list[list[list[str]]]]],
    after: list[list[list[list[list[str]]]]],
    target: tuple[int, int, int, int, int],
) -> None:
    assert len(before) == len(after)
    for section_index, (before_tables, after_tables) in enumerate(zip(before, after, strict=True)):
        assert len(before_tables) == len(after_tables)
        for table_index, (before_table, after_table) in enumerate(
            zip(before_tables, after_tables, strict=True)
        ):
            assert len(before_table) == len(after_table)
            for row_index, (before_row, after_row) in enumerate(
                zip(before_table, after_table, strict=True)
            ):
                assert len(before_row) == len(after_row)
                for cell_index, (before_cell, after_cell) in enumerate(
                    zip(before_row, after_row, strict=True)
                ):
                    assert len(before_cell) == len(after_cell)
                    for paragraph_index, (before_paragraph, after_paragraph) in enumerate(
                        zip(before_cell, after_cell, strict=True)
                    ):
                        if (
                            section_index,
                            table_index,
                            row_index,
                            cell_index,
                            paragraph_index,
                        ) == target:
                            continue
                        assert after_paragraph == before_paragraph


@pytest.mark.unit
def test_replace_table_cell_paragraph_noop_same_length(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()
    before = extract_section_tables(raw_bytes)
    section, table, row, cell, paragraph, text = _first_nonempty_cell_paragraph(before)

    edited = replace_table_cell_paragraph(raw_bytes, section, table, row, cell, paragraph, text)
    after = extract_section_tables(edited)

    assert after == before


@pytest.mark.unit
def test_replace_table_cell_paragraph_changes_target_cell(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()
    before = extract_section_tables(raw_bytes)
    section, table, row, cell, paragraph, _text = _first_nonempty_cell_paragraph(before)

    edited = replace_table_cell_paragraph(
        raw_bytes,
        section,
        table,
        row,
        cell,
        paragraph,
        "수정된 셀",
    )
    after = extract_section_tables(edited)

    assert after[section][table][row][cell][paragraph] == "수정된 셀"


@pytest.mark.unit
def test_replace_table_cell_paragraph_preserves_other_cells(samples_dir: Path) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()
    before = extract_section_tables(raw_bytes)
    section, table, row, cell, paragraph, _text = _first_nonempty_cell_paragraph(before)

    edited = replace_table_cell_paragraph(
        raw_bytes,
        section,
        table,
        row,
        cell,
        paragraph,
        "셀만 변경",
    )
    after = extract_section_tables(edited)

    _assert_other_cells_unchanged(before, after, (section, table, row, cell, paragraph))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("table_index", "row_index", "cell_index", "paragraph_index", "match"),
    [
        (999, 0, 0, 0, "table_index"),
        (0, 999, 0, 0, "row_index"),
        (0, 0, 999, 0, "cell_index"),
        (0, 0, 0, 999, "paragraph_index"),
    ],
)
def test_replace_table_cell_paragraph_out_of_range_raises(
    samples_dir: Path,
    table_index: int,
    row_index: int,
    cell_index: int,
    paragraph_index: int,
    match: str,
) -> None:
    raw_bytes = (samples_dir / "public-official" / "table-vpos-01.hwpx").read_bytes()

    with pytest.raises(IndexError, match=match):
        replace_table_cell_paragraph(
            raw_bytes,
            0,
            table_index,
            row_index,
            cell_index,
            paragraph_index,
            "ignored",
        )
