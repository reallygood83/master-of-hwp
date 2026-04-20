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
from enum import Enum
from pathlib import Path
from typing import Self


class SourceFormat(str, Enum):
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
