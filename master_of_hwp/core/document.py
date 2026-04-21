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

import re
from collections.abc import Iterator
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

    def replace_paragraph(
        self,
        section_index: int,
        paragraph_index: int,
        new_text: str,
    ) -> Self:
        """Return a new `HwpDocument` with the specified paragraph replaced.

        The original instance is not modified (immutable semantics).
        Only the paragraph text is changed; all other document content
        (other paragraphs, tables, styles, non-BodyText storages) is
        preserved as faithfully as the underlying adapter allows.

        Args:
            section_index: Zero-based section index; must be in range
                `[0, sections_count)`.
            paragraph_index: Zero-based paragraph index within the
                target section.
            new_text: Replacement text. Must not contain control
                characters; for HWPX, newlines are preserved as-is.

        Returns:
            A new `HwpDocument` with the updated `raw_bytes`.

        Raises:
            IndexError: If either index is out of range.
            master_of_hwp.adapters.hwp5_reader.Hwp5FormatError:
                For HWP 5.0 if a non-no-op replacement is attempted
                (different-length edits require the CFBF resize writer,
                pending in a future release).
            master_of_hwp.adapters.hwpx_reader.HwpxFormatError:
                If the HWPX container cannot be rewritten.
        """
        from master_of_hwp.adapters.hwp5_reader import (
            replace_paragraph as _hwp5_replace,
        )
        from master_of_hwp.adapters.hwpx_reader import (
            replace_paragraph as _hwpx_replace,
        )

        if self.source_format is SourceFormat.HWP:
            new_bytes = _hwp5_replace(self.raw_bytes, section_index, paragraph_index, new_text)
        elif self.source_format is SourceFormat.HWPX:
            new_bytes = _hwpx_replace(self.raw_bytes, section_index, paragraph_index, new_text)
        else:
            raise AssertionError(f"Unhandled source_format: {self.source_format!r}")

        return type(self)(
            path=self.path,
            source_format=self.source_format,
            raw_bytes=new_bytes,
        )

    def replace_table_cell_paragraph(
        self,
        section_index: int,
        table_index: int,
        row_index: int,
        cell_index: int,
        paragraph_index: int,
        new_text: str,
    ) -> Self:
        """Return a new document with one table cell paragraph replaced.

        HWPX is supported in v0.2. HWP 5.0 raises `NotImplementedError`
        until the richer write path can preserve compound-file table
        structure safely.
        """
        if self.source_format is SourceFormat.HWP:
            raise NotImplementedError("HWP 5.0 table cell editing pending v0.2.x")
        if self.source_format is SourceFormat.HWPX:
            from master_of_hwp.adapters.hwpx_reader import (
                replace_table_cell_paragraph as _hwpx_replace_table_cell,
            )

            new_bytes = _hwpx_replace_table_cell(
                self.raw_bytes,
                section_index,
                table_index,
                row_index,
                cell_index,
                paragraph_index,
                new_text,
            )
            return type(self)(
                path=self.path,
                source_format=self.source_format,
                raw_bytes=new_bytes,
            )
        raise AssertionError(f"Unhandled source_format: {self.source_format!r}")

    @property
    def plain_text(self) -> str:
        """Concatenate all sections into a single format-agnostic string.

        Section boundaries are joined with `"\\n\\n"` (blank line). HWP 5.0
        paragraph terminators (`\\r`) are normalized to `\\n` so the output
        is directly comparable across formats.

        Returns:
            One string representing the document's readable text.

        Raises:
            master_of_hwp.adapters.hwp5_reader.Hwp5FormatError:
                If the HWP 5.0 binary cannot be parsed.
            master_of_hwp.adapters.hwpx_reader.HwpxFormatError:
                If the HWPX container is malformed.

        Example:
            >>> doc = HwpDocument.open("report.hwpx")
            >>> print(doc.plain_text[:50])
        """
        sections = self.section_texts
        if self.source_format is SourceFormat.HWP:
            sections = [section.replace("\r", "\n") for section in sections]
        return "\n\n".join(sections)

    def iter_paragraphs(self) -> Iterator[tuple[int, int, str]]:
        """Iterate over every paragraph in document order.

        Yields:
            `(section_index, paragraph_index, text)` tuples. Empty
            paragraphs are yielded as well (HWPX may preserve them for
            layout intent).

        Example:
            >>> for s, p, text in doc.iter_paragraphs():
            ...     if "TODO" in text:
            ...         print(f"§{s}.{p}: {text}")
        """
        for section_index, paragraphs in enumerate(self.section_paragraphs):
            for paragraph_index, text in enumerate(paragraphs):
                yield section_index, paragraph_index, text

    def find_paragraphs(
        self,
        query: str,
        *,
        regex: bool = False,
        case_sensitive: bool = True,
    ) -> list[tuple[int, int, str]]:
        """Find paragraphs whose text matches `query`.

        Args:
            query: Substring (default) or regex pattern (when `regex=True`).
            regex: Treat `query` as a regular expression (anchored with
                `re.search`, not `re.fullmatch`).
            case_sensitive: When `False`, match case-insensitively.

        Returns:
            List of `(section_index, paragraph_index, text)` for every
            matching paragraph, in document order.

        Raises:
            re.error: If `regex=True` and `query` is not a valid pattern.

        Example:
            >>> hits = doc.find_paragraphs("보도자료")
            >>> for s, p, text in hits:
            ...     print(f"§{s}.{p}: {text}")
        """
        if regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query, flags)
            return [
                (s, p, text)
                for s, p, text in self.iter_paragraphs()
                if pattern.search(text) is not None
            ]

        if case_sensitive:
            return [(s, p, text) for s, p, text in self.iter_paragraphs() if query in text]
        needle = query.lower()
        return [(s, p, text) for s, p, text in self.iter_paragraphs() if needle in text.lower()]

    def summary(self, *, max_preview: int = 80, preview_count: int = 3) -> dict[str, object]:
        """Return a compact structural overview for AI context or logs.

        The returned dict is JSON-serializable and intended to be
        included in LLM prompts as a "what kind of document is this"
        briefing. The full path is deliberately omitted (privacy).

        Args:
            max_preview: Maximum character length of each preview string.
            preview_count: Maximum number of non-empty paragraph
                previews to include.

        Returns:
            A dict with keys:
              - `format`: "hwp" or "hwpx"
              - `filename`: basename of `self.path` (not the full path)
              - `byte_size`: size of `raw_bytes` in bytes
              - `sections_count`: number of sections
              - `paragraph_count`: total paragraphs across all sections
              - `non_empty_paragraph_count`: paragraphs with at least
                one non-whitespace character
              - `table_count`: total tables across all sections
              - `first_paragraphs`: up to `preview_count` non-empty
                paragraph previews, each truncated to `max_preview`

        Raises:
            master_of_hwp.adapters.hwp5_reader.Hwp5FormatError:
                If the HWP 5.0 binary cannot be parsed.
            master_of_hwp.adapters.hwpx_reader.HwpxFormatError:
                If the HWPX container is malformed.

        Example:
            >>> info = doc.summary()
            >>> print(info["sections_count"], info["non_empty_paragraph_count"])
        """
        paragraphs = self.section_paragraphs
        total_paragraphs = sum(len(s) for s in paragraphs)
        non_empty = [text for section in paragraphs for text in section if text.strip()]
        previews = [text[:max_preview] for text in non_empty[:preview_count]]
        table_count = sum(len(section) for section in self.section_tables)
        return {
            "format": self.source_format.value,
            "filename": self.path.name,
            "byte_size": self.byte_size,
            "sections_count": self.sections_count,
            "paragraph_count": total_paragraphs,
            "non_empty_paragraph_count": len(non_empty),
            "table_count": table_count,
            "first_paragraphs": previews,
        }
