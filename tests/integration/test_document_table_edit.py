"""Integration tests for HwpDocument table cell paragraph replacement."""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp import HwpDocument

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def hwpx_sample(samples_dir: Path) -> Path:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
    if not sample.exists():
        pytest.skip("HWPX sample missing")
    return sample


@pytest.fixture(scope="module")
def hwp_sample(samples_dir: Path) -> Path:
    sample = samples_dir / "public-official" / "re-mixed-0tr.hwp"
    if not sample.exists():
        pytest.skip("HWP 5.0 sample missing")
    return sample


def test_document_replace_table_cell_paragraph_updates_hwpx(hwpx_sample: Path) -> None:
    doc = HwpDocument.open(hwpx_sample)
    edited = doc.replace_table_cell_paragraph(0, 0, 0, 1, 0, "문서 API 셀 수정")

    assert edited is not doc
    assert edited.section_tables[0][0][0][1][0] == "문서 API 셀 수정"


def test_document_replace_table_cell_paragraph_hwp_raises(hwp_sample: Path) -> None:
    doc = HwpDocument.open(hwp_sample)

    with pytest.raises(NotImplementedError, match="HWP 5.0 table cell editing"):
        doc.replace_table_cell_paragraph(0, 0, 0, 0, 0, "unsupported")
