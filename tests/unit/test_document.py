"""Unit tests for master_of_hwp.core.document."""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp import HwpDocument
from master_of_hwp.core.document import DocumentOpenError, SourceFormat


@pytest.mark.unit
class TestSourceFormat:
    @pytest.mark.parametrize(
        ("suffix", "expected"),
        [
            ("hwp", SourceFormat.HWP),
            (".hwp", SourceFormat.HWP),
            ("HWP", SourceFormat.HWP),
            ("hwpx", SourceFormat.HWPX),
            (".HWPX", SourceFormat.HWPX),
        ],
    )
    def test_from_suffix_supported(self, suffix: str, expected: SourceFormat) -> None:
        assert SourceFormat.from_suffix(suffix) is expected

    @pytest.mark.parametrize("suffix", ["docx", "txt", "", ".pdf"])
    def test_from_suffix_rejects_unsupported(self, suffix: str) -> None:
        with pytest.raises(ValueError, match="Unsupported HWP suffix"):
            SourceFormat.from_suffix(suffix)


@pytest.mark.unit
class TestHwpDocumentOpen:
    def test_open_classifies_hwpx(self, tmp_hwpx: Path) -> None:
        doc = HwpDocument.open(tmp_hwpx)
        assert doc.source_format is SourceFormat.HWPX
        assert doc.path == tmp_hwpx
        assert doc.byte_size == len(tmp_hwpx.read_bytes())

    def test_open_missing_file_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.hwp"
        with pytest.raises(DocumentOpenError, match="File not found"):
            HwpDocument.open(missing)

    def test_open_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DocumentOpenError, match="Not a regular file"):
            HwpDocument.open(tmp_path)

    def test_open_unsupported_suffix_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "notes.txt"
        bad.write_text("hello")
        with pytest.raises(DocumentOpenError, match="Unsupported HWP suffix"):
            HwpDocument.open(bad)

    def test_open_returns_immutable(self, tmp_hwpx: Path) -> None:
        doc = HwpDocument.open(tmp_hwpx)
        with pytest.raises((AttributeError, TypeError)):
            doc.path = Path("/somewhere/else")  # type: ignore[misc]
