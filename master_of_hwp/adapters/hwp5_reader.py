"""Minimal HWP 5.0 reader utilities backed by compound-file inspection."""

from __future__ import annotations

import re
import zlib
from collections.abc import Iterator
from io import BytesIO
from typing import Any

import olefile
from olefile import OleFileIO
from olefile.olefile import OleFileError

_SECTION_NAME_PATTERN = re.compile(r"Section\d+")
_PARA_TEXT_TAG_ID = 0x43
_TABLE_TAG_ID = 0x5B


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
    try:
        with _open_compound_file(raw_bytes) as compound_file:
            section_count = len(_list_section_streams(compound_file))
    except OSError as exc:
        raise Hwp5FormatError(f"Failed to read HWP 5.0 compound file: {exc}") from exc
    except OleFileError as exc:
        raise Hwp5FormatError(f"Invalid HWP 5.0 compound structure: {exc}") from exc

    if section_count < 1:
        raise Hwp5FormatError("HWP 5.0 BodyText storage does not contain Section streams.")
    return section_count


def extract_section_texts(raw_bytes: bytes) -> list[str]:
    """Return the plain text of each BodyText/Section stream.

    Args:
        raw_bytes: The exact bytes of a `.hwp` binary document.

    Returns:
        One plain-text string per `BodyText/SectionN` stream.

    Raises:
        ValueError: If `raw_bytes` is empty.
        Hwp5FormatError: If the payload is not a readable HWP 5.0 compound
            file or one of its section streams is malformed.
    """
    try:
        with _open_compound_file(raw_bytes) as compound_file:
            section_names = _list_section_streams(compound_file)
            texts = [
                _extract_section_stream_text(
                    compound_file.openstream(["BodyText", section_name]).read()
                )
                for section_name in section_names
            ]
    except OSError as exc:
        raise Hwp5FormatError(f"Failed to read HWP 5.0 compound file: {exc}") from exc
    except OleFileError as exc:
        raise Hwp5FormatError(f"Invalid HWP 5.0 compound structure: {exc}") from exc

    if len(texts) != len(section_names):
        raise Hwp5FormatError("Extracted section text count does not match BodyText section count.")
    return texts


def extract_section_paragraphs(raw_bytes: bytes) -> list[list[str]]:
    """Return paragraphs per HWP 5.0 section stream.

    Args:
        raw_bytes: The exact bytes of a `.hwp` binary document.

    Returns:
        Outer list: one entry per `BodyText/SectionN` stream.
        Inner list: one string per paragraph, based on `PARA_TEXT` records.

    Raises:
        ValueError: If `raw_bytes` is empty.
        Hwp5FormatError: If the payload is not a readable HWP 5.0 compound
            file or one of its section streams is malformed.
    """
    try:
        with _open_compound_file(raw_bytes) as compound_file:
            section_names = _list_section_streams(compound_file)
            paragraphs = [
                _extract_section_stream_paragraphs(
                    compound_file.openstream(["BodyText", section_name]).read()
                )
                for section_name in section_names
            ]
    except OSError as exc:
        raise Hwp5FormatError(f"Failed to read HWP 5.0 compound file: {exc}") from exc
    except OleFileError as exc:
        raise Hwp5FormatError(f"Invalid HWP 5.0 compound structure: {exc}") from exc

    if len(paragraphs) != len(section_names):
        raise Hwp5FormatError(
            "Extracted section paragraph count does not match BodyText section count."
        )
    return paragraphs


def extract_section_tables(raw_bytes: bytes) -> list[list[list[list[list[str]]]]]:
    """Return tables per HWP 5.0 section stream.

    Args:
        raw_bytes: The exact bytes of a `.hwp` binary document.

    Returns:
        Outermost list: one entry per `BodyText/SectionN` stream.
        Then tables, rows, and cells where each cell is a list of paragraphs.

    Raises:
        ValueError: If `raw_bytes` is empty.
        Hwp5FormatError: If the payload is not a readable HWP 5.0 compound
            file or one of its section streams is malformed.
    """
    try:
        with _open_compound_file(raw_bytes) as compound_file:
            section_names = _list_section_streams(compound_file)
            tables = [
                _extract_section_stream_tables(
                    compound_file.openstream(["BodyText", section_name]).read()
                )
                for section_name in section_names
            ]
    except OSError as exc:
        raise Hwp5FormatError(f"Failed to read HWP 5.0 compound file: {exc}") from exc
    except OleFileError as exc:
        raise Hwp5FormatError(f"Invalid HWP 5.0 compound structure: {exc}") from exc

    if len(tables) != len(section_names):
        raise Hwp5FormatError(
            "Extracted section table count does not match BodyText section count."
        )
    return tables


def _open_compound_file(raw_bytes: bytes) -> OleFileIO[Any]:
    if not raw_bytes:
        raise ValueError("HWP raw_bytes must not be empty.")
    if not olefile.isOleFile(data=raw_bytes):
        raise Hwp5FormatError("Not a valid HWP 5.0 compound file.")
    return olefile.OleFileIO(BytesIO(raw_bytes))


def _list_section_streams(compound_file: OleFileIO[Any]) -> list[str]:
    section_names = [
        entry[1]
        for entry in compound_file.listdir()
        if len(entry) == 2
        and entry[0] == "BodyText"
        and _SECTION_NAME_PATTERN.fullmatch(entry[1]) is not None
    ]
    section_names.sort(key=_section_index)
    return section_names


def _section_index(section_name: str) -> int:
    return int(section_name.removeprefix("Section"))


def _extract_section_stream_text(raw_section: bytes) -> str:
    decompressed = _decompress_section(raw_section)
    return "".join(
        _decode_para_text(record_payload)
        for tag_id, _level, record_payload in _iter_records(decompressed)
        if tag_id == _PARA_TEXT_TAG_ID
    )


def _extract_section_stream_paragraphs(raw_section: bytes) -> list[str]:
    decompressed = _decompress_section(raw_section)
    return [
        _decode_para_text(record_payload).removesuffix("\r")
        for tag_id, _level, record_payload in _iter_records(decompressed)
        if tag_id == _PARA_TEXT_TAG_ID
    ]


def _extract_section_stream_tables(raw_section: bytes) -> list[list[list[list[str]]]]:
    decompressed = _decompress_section(raw_section)
    tables: list[list[list[list[str]]]] = []
    current_table_level: int | None = None
    current_table_paragraphs: list[str] = []
    for tag_id, level, record_payload in _iter_records(decompressed):
        if (
            current_table_level is not None
            and tag_id == _TABLE_TAG_ID
            and level <= current_table_level
        ):
            tables.append(_materialize_minimal_table(current_table_paragraphs))
            current_table_level = None
            current_table_paragraphs = []
        if tag_id == _TABLE_TAG_ID:
            current_table_level = level
            current_table_paragraphs = []
            continue
        if current_table_level is None:
            continue
        if level <= current_table_level:
            tables.append(_materialize_minimal_table(current_table_paragraphs))
            current_table_level = None
            current_table_paragraphs = []
            continue
        if tag_id == _PARA_TEXT_TAG_ID:
            current_table_paragraphs.append(_decode_para_text(record_payload).removesuffix("\r"))
    if current_table_level is not None:
        tables.append(_materialize_minimal_table(current_table_paragraphs))
    return tables


def _materialize_minimal_table(paragraphs: list[str]) -> list[list[list[str]]]:
    if not paragraphs:
        return []
    return [[paragraphs]]


def _decompress_section(raw_section: bytes) -> bytes:
    try:
        return zlib.decompress(raw_section, wbits=-15)
    except zlib.error:
        try:
            return zlib.decompress(raw_section)
        except zlib.error as exc:
            raise Hwp5FormatError(f"Failed to decompress HWP section stream: {exc}") from exc


def _iter_records(stream: bytes) -> Iterator[tuple[int, int, bytes]]:
    offset = 0
    while offset + 4 <= len(stream):
        header = int.from_bytes(stream[offset : offset + 4], "little")
        tag_id = header & 0x3FF
        level = (header >> 10) & 0x3FF
        size = (header >> 20) & 0xFFF
        offset += 4
        if size == 0xFFF:
            if offset + 4 > len(stream):
                raise Hwp5FormatError("Truncated extended-size HWP record header.")
            size = int.from_bytes(stream[offset : offset + 4], "little")
            offset += 4
        if offset + size > len(stream):
            raise Hwp5FormatError("Truncated HWP record payload.")
        payload = stream[offset : offset + size]
        offset += size
        yield tag_id, level, payload
    if offset != len(stream):
        raise Hwp5FormatError("Trailing bytes remain after parsing HWP records.")


def _decode_para_text(payload: bytes) -> str:
    if len(payload) % 2 != 0:
        raise Hwp5FormatError("PARA_TEXT payload has odd byte length.")
    code_units = [
        int.from_bytes(payload[index : index + 2], "little") for index in range(0, len(payload), 2)
    ]
    characters: list[str] = []
    index = 0
    while index < len(code_units):
        code_unit = code_units[index]
        if code_unit in {0x0009, 0x000A, 0x000D}:
            characters.append(chr(code_unit))
            index += 1
            continue
        if code_unit < 0x0020:
            index += 8 if index + 7 < len(code_units) else 1
            continue
        characters.append(chr(code_unit))
        index += 1
    return "".join(characters)
