"""Minimal HWP 5.0 reader utilities backed by compound-file inspection."""

from __future__ import annotations

import re
from io import BytesIO

import olefile
from olefile.olefile import OleFileError

_SECTION_NAME_PATTERN = re.compile(r"Section\d+")


class Hwp5FormatError(ValueError):
    """Raised when raw bytes are not a readable HWP 5.0 compound document."""


def count_sections(raw_bytes: bytes) -> int:
    """Return the number of `BodyText/Section*` streams in a HWP 5.0 file.

    Args:
        raw_bytes: The exact bytes of a `.hwp` binary document.

    Returns:
        The number of section streams stored below the `BodyText` storage.

    Raises:
        ValueError: If `raw_bytes` is empty.
        Hwp5FormatError: If the payload is not a readable HWP 5.0 compound
            file or does not expose any `BodyText/Section*` streams.
    """
    if not raw_bytes:
        raise ValueError("HWP raw_bytes must not be empty.")
    if not olefile.isOleFile(data=raw_bytes):
        raise Hwp5FormatError("Not a valid HWP 5.0 compound file.")

    try:
        with olefile.OleFileIO(BytesIO(raw_bytes)) as compound_file:
            section_count = sum(
                1
                for entry in compound_file.listdir()
                if len(entry) == 2
                and entry[0] == "BodyText"
                and _SECTION_NAME_PATTERN.fullmatch(entry[1]) is not None
            )
    except OSError as exc:
        raise Hwp5FormatError(f"Failed to read HWP 5.0 compound file: {exc}") from exc
    except OleFileError as exc:
        raise Hwp5FormatError(f"Invalid HWP 5.0 compound structure: {exc}") from exc

    if section_count < 1:
        raise Hwp5FormatError("HWP 5.0 BodyText storage does not contain Section streams.")
    return section_count
