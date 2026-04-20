"""Minimal HWPX reader utilities backed by ZIP container inspection."""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from io import BytesIO
from xml.etree import ElementTree

_SECTION_PART_PATTERN = re.compile(r"Contents/section(\d+)\.xml", re.IGNORECASE)
_SECTION_HREF_PATTERN = re.compile(r"(?:^|.*/)section\d+\.xml$", re.IGNORECASE)


class HwpxFormatError(ValueError):
    """Raised when raw bytes are not a readable HWPX/ZIP document."""


def count_sections(raw_bytes: bytes) -> int:
    """Return the number of section XML parts in a HWPX file.

    Args:
        raw_bytes: The exact bytes of a `.hwpx` ZIP container.

    Returns:
        The number of section XML parts declared by the archive.

    Raises:
        ValueError: If `raw_bytes` is empty.
        HwpxFormatError: If the payload is not a readable HWPX container or
            does not expose any section parts.
    """
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")

    try:
        with zipfile.ZipFile(BytesIO(raw_bytes)) as archive:
            return len(_list_section_part_names(archive))
    except zipfile.BadZipFile as exc:
        raise HwpxFormatError(f"Not a valid HWPX (ZIP) container: {exc}") from exc
    except OSError as exc:
        raise HwpxFormatError(f"Failed to read HWPX container: {exc}") from exc


def extract_section_texts(raw_bytes: bytes) -> list[str]:
    """Return the plain text of each HWPX section XML part.

    Args:
        raw_bytes: The exact bytes of a `.hwpx` ZIP container.

    Returns:
        One plain-text string per section XML part.

    Raises:
        ValueError: If `raw_bytes` is empty.
        HwpxFormatError: If the payload is not a readable HWPX container or
            one of its section XML parts is malformed.
    """
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")

    section_paragraphs = extract_section_paragraphs(raw_bytes)
    return ["\n".join(paragraphs) for paragraphs in section_paragraphs]


def extract_section_paragraphs(raw_bytes: bytes) -> list[list[str]]:
    """Return paragraphs per HWPX section XML part.

    Args:
        raw_bytes: The exact bytes of a `.hwpx` ZIP container.

    Returns:
        Outer list: one entry per section XML part.
        Inner list: one string per `<p>` element.

    Raises:
        ValueError: If `raw_bytes` is empty.
        HwpxFormatError: If the payload is not a readable HWPX container or
            one of its section XML parts is malformed.
    """
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")

    try:
        with zipfile.ZipFile(BytesIO(raw_bytes)) as archive:
            section_names = _list_section_part_names(archive)
            paragraphs = [
                _paragraphs_from_section_xml(archive.read(name)) for name in section_names
            ]
    except zipfile.BadZipFile as exc:
        raise HwpxFormatError(f"Not a valid HWPX (ZIP) container: {exc}") from exc
    except KeyError as exc:
        raise HwpxFormatError(f"HWPX section part is missing from the archive: {exc}") from exc
    except OSError as exc:
        raise HwpxFormatError(f"Failed to read HWPX container: {exc}") from exc

    if len(paragraphs) != len(section_names):
        raise HwpxFormatError(
            "Extracted HWPX section paragraph count does not match section count."
        )
    return paragraphs


def _list_section_part_names(archive: zipfile.ZipFile) -> list[str]:
    section_entries = sorted(
        (
            (int(match.group(1)), name)
            for name in archive.namelist()
            if (match := _SECTION_PART_PATTERN.fullmatch(name)) is not None
        ),
        key=lambda entry: entry[0],
    )
    if section_entries:
        return [name for _index, name in section_entries]
    return _list_manifest_section_part_names(_read_manifest_bytes(archive))


def _read_manifest_bytes(archive: zipfile.ZipFile) -> bytes:
    try:
        return archive.read("Contents/content.hpf")
    except KeyError as exc:
        raise HwpxFormatError(
            "HWPX container has no Contents/sectionN.xml entries or content.hpf " "manifest."
        ) from exc


def _list_manifest_section_part_names(manifest_bytes: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(manifest_bytes)
    except ElementTree.ParseError as exc:
        raise HwpxFormatError(f"Invalid HWPX content.hpf manifest: {exc}") from exc

    id_to_href = _manifest_section_href_map(root.iter())
    ordered_hrefs = [
        id_to_href[idref]
        for idref in (
            element.attrib.get("idref")
            for element in root.iter()
            if _local_name(element.tag) == "itemref"
        )
        if idref in id_to_href
    ]
    if ordered_hrefs:
        return ordered_hrefs
    if id_to_href:
        return list(id_to_href.values())
    raise HwpxFormatError("HWPX container has no Contents/sectionN.xml entries.")


def _manifest_section_href_map(elements: Iterator[ElementTree.Element]) -> dict[str, str]:
    return {
        element.attrib["id"]: element.attrib["href"]
        for element in elements
        if _local_name(element.tag) == "item"
        and "id" in element.attrib
        and "href" in element.attrib
        and _SECTION_HREF_PATTERN.fullmatch(element.attrib["href"]) is not None
    }


def _extract_text_from_section_xml(xml_bytes: bytes) -> str:
    return "\n".join(_paragraphs_from_section_xml(xml_bytes))


def _paragraphs_from_section_xml(xml_bytes: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise HwpxFormatError(f"Invalid HWPX section XML: {exc}") from exc

    return [
        "".join(text for text in _iter_paragraph_text_nodes(paragraph) if text)
        for paragraph in root.iter()
        if _local_name(paragraph.tag) == "p"
    ]


def _iter_paragraph_text_nodes(paragraph: ElementTree.Element) -> Iterator[str]:
    for element in paragraph.iter():
        if _local_name(element.tag) == "t":
            yield element.text or ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]
