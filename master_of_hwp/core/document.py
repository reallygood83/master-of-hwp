"""HwpDocument — the central domain type of master_of_hwp.

Philosophy:
    * Immutable (frozen dataclass): any edit returns a new HwpDocument.
    * Format-agnostic: .hwp (binary compound) and .hwpx (OOXML zip) are
      discriminated by `source_format`; consumers should not branch on the
      raw bytes.
    * Lazy parsing: the document holds raw bytes plus cached parse artifacts.
      Heavy work happens only when the caller asks for structural accessors.

This module is intentionally small. Section/Paragraph/Table types live
alongside it and are added in Phase 1 as the parse path is wired up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Self


class SourceFormat(StrEnum):
    """Supported HWP document formats."""

    HWP = "hwp"
    HWPX = "hwpx"

    @classmethod
    def from_suffix(cls, suffix: str) -> SourceFormat:
        """Classify a file by its suffix (case-insensitive, leading dot optional)."""
        normalized = suffix.lower().lstrip(".")
        if normalized == "hwp":
            return cls.HWP
        if normalized == "hwpx":
            return cls.HWPX
        raise ValueError(f"Unsupported HWP suffix: {suffix!r}")


class DocumentOpenError(Exception):
    """Raised when a document cannot be opened or is unreadable."""


@dataclass(frozen=True)
class HwpDocument:
    """An in-memory representation of a HWP/HWPX document.

    This is the public entry point for all read and edit operations.
    Instances are immutable; edits produce new instances.

    Attributes:
        path: Absolute path the document was loaded from.
        source_format: Whether the document is .hwp (binary) or .hwpx (XML).
        raw_bytes: The exact byte sequence read from disk. Edits do not
            modify this field; it is retained for fidelity verification.

    Example:
        >>> doc = HwpDocument.open("samples/teacher/notice.hwp")
        >>> doc.source_format
        <SourceFormat.HWP: 'hwp'>
    """

    path: Path
    source_format: SourceFormat
    raw_bytes: bytes = field(repr=False)

    @classmethod
    def open(cls, path: str | Path) -> Self:
        """Open a document from disk.

        Args:
            path: Path to a .hwp or .hwpx file.

        Returns:
            A new HwpDocument instance.

        Raises:
            DocumentOpenError: If the path does not exist, is not a file,
                or has an unsupported suffix.
        """
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise DocumentOpenError(f"File not found: {resolved}")
        if not resolved.is_file():
            raise DocumentOpenError(f"Not a regular file: {resolved}")
        try:
            source_format = SourceFormat.from_suffix(resolved.suffix)
        except ValueError as exc:
            raise DocumentOpenError(str(exc)) from exc
        try:
            raw_bytes = resolved.read_bytes()
        except OSError as exc:
            raise DocumentOpenError(f"Failed to read {resolved}: {exc}") from exc
        return cls(path=resolved, source_format=source_format, raw_bytes=raw_bytes)

    @property
    def byte_size(self) -> int:
        """Size of the raw bytes in memory."""
        return len(self.raw_bytes)

    @property
    def sections_count(self) -> int:
        """Number of sections in the document.

        Dispatches to the format-specific reader. Both readers share the
        invariant `count_sections -> int >= 1`; a value of 0 never occurs
        because malformed inputs raise a `*FormatError` instead.

        Returns:
            The number of sections (HWP 5.0 `BodyText/SectionN` streams, or
            HWPX `Contents/sectionN.xml` parts / OPF spine entries).

        Raises:
            master_of_hwp.adapters.hwp5_reader.Hwp5FormatError:
                If the HWP 5.0 binary is malformed.
            master_of_hwp.adapters.hwpx_reader.HwpxFormatError:
                If the HWPX container is malformed.
        """
        from master_of_hwp.adapters.hwp5_reader import (
            count_sections as _hwp5_count,
        )
        from master_of_hwp.adapters.hwpx_reader import (
            count_sections as _hwpx_count,
        )

        if self.source_format is SourceFormat.HWP:
            return _hwp5_count(self.raw_bytes)
        if self.source_format is SourceFormat.HWPX:
            return _hwpx_count(self.raw_bytes)
        raise AssertionError(f"Unhandled source_format: {self.source_format!r}")

    @property
    def section_texts(self) -> list[str]:
        """Plain text of each section, one string per section.

        Returns:
            A list of strings; `len(section_texts) == sections_count`.
            HWP 5.0 paragraph terminators (`\\r`) are preserved as-is;
            HWPX paragraph boundaries are emitted as `\\n`. Consumers
            that want a single normalized separator should post-process.

        Raises:
            master_of_hwp.adapters.hwp5_reader.Hwp5FormatError:
                If the HWP 5.0 binary cannot be parsed.
            master_of_hwp.adapters.hwpx_reader.HwpxFormatError:
                If the HWPX container is malformed.
        """
        from master_of_hwp.adapters.hwp5_reader import (
            extract_section_texts as _hwp5_extract,
        )
        from master_of_hwp.adapters.hwpx_reader import (
            extract_section_texts as _hwpx_extract,
        )

        if self.source_format is SourceFormat.HWP:
            return _hwp5_extract(self.raw_bytes)
        if self.source_format is SourceFormat.HWPX:
            return _hwpx_extract(self.raw_bytes)
        raise AssertionError(f"Unhandled source_format: {self.source_format!r}")

    @property
    def section_paragraphs(self) -> list[list[str]]:
        """Paragraphs of each section, as nested lists.

        Returns:
            Outer list: one entry per section; `len == sections_count`.
            Inner list: one string per paragraph. HWP 5.0 paragraph
            terminators (`\\r`) are stripped; HWPX preserves empty
            paragraphs as `""` to retain layout intent.

        Raises:
            master_of_hwp.adapters.hwp5_reader.Hwp5FormatError:
                If the HWP 5.0 binary cannot be parsed.
            master_of_hwp.adapters.hwpx_reader.HwpxFormatError:
                If the HWPX container is malformed.
        """
        from master_of_hwp.adapters.hwp5_reader import (
            extract_section_paragraphs as _hwp5_paragraphs,
        )
        from master_of_hwp.adapters.hwpx_reader import (
            extract_section_paragraphs as _hwpx_paragraphs,
        )

        if self.source_format is SourceFormat.HWP:
            return _hwp5_paragraphs(self.raw_bytes)
        if self.source_format is SourceFormat.HWPX:
            return _hwpx_paragraphs(self.raw_bytes)
        raise AssertionError(f"Unhandled source_format: {self.source_format!r}")

    @property
    def section_tables(self) -> list[list[list[list[list[str]]]]]:
        """Tables per section as a 5-level nested list.

        Returns:
            `[section][table][row][cell][paragraph]`. Outermost length
            equals `sections_count`. Each cell is itself a list of
            paragraph strings (reusing the paragraph enumeration
            contract). Sections with no tables return an empty list
            (never a placeholder structure).

        Raises:
            master_of_hwp.adapters.hwp5_reader.Hwp5FormatError:
                If the HWP 5.0 binary cannot be parsed.
            master_of_hwp.adapters.hwpx_reader.HwpxFormatError:
                If the HWPX container is malformed.

        Notes:
            HWP 5.0 table extraction is currently a minimal heuristic
            anchored on the `TABLE(0x5B)` record; exact row/cell
            recovery is pending a richer record-level parser.
        """
        from master_of_hwp.adapters.hwp5_reader import (
            extract_section_tables as _hwp5_tables,
        )
        from master_of_hwp.adapters.hwpx_reader import (
            extract_section_tables as _hwpx_tables,
        )

        if self.source_format is SourceFormat.HWP:
            return _hwp5_tables(self.raw_bytes)
        if self.source_format is SourceFormat.HWPX:
            return _hwpx_tables(self.raw_bytes)
        raise AssertionError(f"Unhandled source_format: {self.source_format!r}")
