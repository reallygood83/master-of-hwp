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


def extract_section_tables(raw_bytes: bytes) -> list[list[list[list[list[str]]]]]:
    """Return tables per HWPX section XML part.

    Args:
        raw_bytes: The exact bytes of a `.hwpx` ZIP container.

    Returns:
        Outermost list: one entry per section XML part.
        Then tables, rows, and cells where each cell is a list of paragraphs.

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
            tables = [_tables_from_section_xml(archive.read(name)) for name in section_names]
    except zipfile.BadZipFile as exc:
        raise HwpxFormatError(f"Not a valid HWPX (ZIP) container: {exc}") from exc
    except KeyError as exc:
        raise HwpxFormatError(f"HWPX section part is missing from the archive: {exc}") from exc
    except OSError as exc:
        raise HwpxFormatError(f"Failed to read HWPX container: {exc}") from exc

    if len(tables) != len(section_names):
        raise HwpxFormatError("Extracted HWPX section table count does not match section count.")
    return tables


def replace_paragraph(
    raw_bytes: bytes,
    section_index: int,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    """Return new raw bytes with the specified paragraph replaced."""
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")

    try:
        with zipfile.ZipFile(BytesIO(raw_bytes)) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
            section_names = _list_section_part_names(archive)
    except zipfile.BadZipFile as exc:
        raise HwpxFormatError(f"Not a valid HWPX (ZIP) container: {exc}") from exc
    except OSError as exc:
        raise HwpxFormatError(f"Failed to read HWPX container: {exc}") from exc

    if not 0 <= section_index < len(section_names):
        raise IndexError(f"section_index {section_index} out of range")
    target_name = section_names[section_index]

    replaced = False
    updated_entries: list[tuple[zipfile.ZipInfo, bytes]] = []
    for info, data in entries:
        if info.filename == target_name:
            updated_entries.append(
                (info, _replace_paragraph_in_section_xml(data, paragraph_index, new_text))
            )
            replaced = True
            continue
        updated_entries.append((info, data))
    if not replaced:
        raise HwpxFormatError(f"HWPX target section part not found: {target_name}")

    output = BytesIO()
    with zipfile.ZipFile(output, "w") as destination:
        for info, data in updated_entries:
            destination.writestr(info, data)
    return output.getvalue()


def replace_table_cell_paragraph(
    raw_bytes: bytes,
    section_index: int,
    table_index: int,
    row_index: int,
    cell_index: int,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    """Return new raw bytes with the targeted table cell paragraph replaced."""
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")

    try:
        with zipfile.ZipFile(BytesIO(raw_bytes)) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
            section_names = _list_section_part_names(archive)
    except zipfile.BadZipFile as exc:
        raise HwpxFormatError(f"Not a valid HWPX (ZIP) container: {exc}") from exc
    except OSError as exc:
        raise HwpxFormatError(f"Failed to read HWPX container: {exc}") from exc

    if not 0 <= section_index < len(section_names):
        raise IndexError(f"section_index {section_index} out of range")
    target_name = section_names[section_index]

    replaced = False
    updated_entries: list[tuple[zipfile.ZipInfo, bytes]] = []
    for info, data in entries:
        if info.filename == target_name:
            updated_entries.append(
                (
                    info,
                    _replace_paragraph_in_table_cell(
                        data,
                        table_index,
                        row_index,
                        cell_index,
                        paragraph_index,
                        new_text,
                    ),
                )
            )
            replaced = True
            continue
        updated_entries.append((info, data))
    if not replaced:
        raise HwpxFormatError(f"HWPX target section part not found: {target_name}")

    output = BytesIO()
    with zipfile.ZipFile(output, "w") as destination:
        for info, data in updated_entries:
            destination.writestr(info, data)
    return output.getvalue()


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


def _replace_paragraph_in_section_xml(
    xml_bytes: bytes,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise HwpxFormatError(f"Invalid HWPX section XML: {exc}") from exc

    paragraphs = [paragraph for paragraph in root.iter() if _local_name(paragraph.tag) == "p"]
    if not 0 <= paragraph_index < len(paragraphs):
        raise IndexError(f"paragraph_index {paragraph_index} out of range")
    _replace_paragraph_text(paragraphs[paragraph_index], new_text)
    return bytes(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))


def _replace_paragraph_in_table_cell(
    xml_bytes: bytes,
    table_index: int,
    row_index: int,
    cell_index: int,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise HwpxFormatError(f"Invalid HWPX section XML: {exc}") from exc

    tables = list(_iter_top_level_tables(root))
    if not 0 <= table_index < len(tables):
        raise IndexError(f"table_index {table_index} out of range")
    rows = [row for row in list(tables[table_index]) if _local_name(row.tag) == "tr"]
    if not 0 <= row_index < len(rows):
        raise IndexError(f"row_index {row_index} out of range")
    cells = [cell for cell in list(rows[row_index]) if _local_name(cell.tag) == "tc"]
    if not 0 <= cell_index < len(cells):
        raise IndexError(f"cell_index {cell_index} out of range")
    paragraphs = list(_iter_cell_paragraphs(cells[cell_index]))
    if not 0 <= paragraph_index < len(paragraphs):
        raise IndexError(f"paragraph_index {paragraph_index} out of range")

    _replace_paragraph_text(paragraphs[paragraph_index], new_text)
    return bytes(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))


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


def _replace_paragraph_text(paragraph: ElementTree.Element, new_text: str) -> None:
    t_elements = list(_iter_paragraph_text_elements(paragraph))
    if t_elements:
        t_elements[0].text = new_text
        parent_map = _build_parent_map(paragraph)
        for extra in t_elements[1:]:
            parent = parent_map.get(extra)
            if parent is not None:
                parent.remove(extra)
        return

    runs = [element for element in paragraph.iter() if _local_name(element.tag) == "run"]
    if runs:
        run = runs[0]
    else:
        run = ElementTree.SubElement(paragraph, _qualified_tag(paragraph.tag, "run"))
    t_element = ElementTree.SubElement(run, _qualified_tag(run.tag, "t"))
    t_element.text = new_text


def _build_parent_map(root: ElementTree.Element) -> dict[ElementTree.Element, ElementTree.Element]:
    return {child: parent for parent in root.iter() for child in list(parent)}


def _tables_from_section_xml(xml_bytes: bytes) -> list[list[list[list[str]]]]:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise HwpxFormatError(f"Invalid HWPX section XML: {exc}") from exc

    return [_table_from_element(table) for table in _iter_top_level_tables(root)]


def _iter_top_level_tables(element: ElementTree.Element) -> Iterator[ElementTree.Element]:
    for child in list(element):
        if _local_name(child.tag) == "tbl":
            yield child
            continue
        yield from _iter_top_level_tables(child)


def _table_from_element(table: ElementTree.Element) -> list[list[list[str]]]:
    return [_row_from_element(row) for row in list(table) if _local_name(row.tag) == "tr"]


def _row_from_element(row: ElementTree.Element) -> list[list[str]]:
    return [
        _cell_paragraphs_from_element(cell) for cell in list(row) if _local_name(cell.tag) == "tc"
    ]


def _cell_paragraphs_from_element(cell: ElementTree.Element) -> list[str]:
    return [
        "".join(text for text in _iter_paragraph_text_nodes(paragraph) if text)
        for paragraph in _iter_cell_paragraphs(cell)
    ]


def _iter_cell_paragraphs(element: ElementTree.Element) -> Iterator[ElementTree.Element]:
    if _local_name(element.tag) == "tbl":
        return
    if _local_name(element.tag) == "p":
        yield element
        return
    for child in list(element):
        yield from _iter_cell_paragraphs(child)


def _iter_paragraph_text_nodes(paragraph: ElementTree.Element) -> Iterator[str]:
    for element in _iter_paragraph_text_elements(paragraph):
        yield element.text or ""


def _iter_paragraph_text_elements(paragraph: ElementTree.Element) -> Iterator[ElementTree.Element]:
    for child in list(paragraph):
        yield from _iter_text_elements_without_nested_paragraphs(child)


def _iter_text_elements_without_nested_paragraphs(
    element: ElementTree.Element,
) -> Iterator[ElementTree.Element]:
    local_name = _local_name(element.tag)
    if local_name == "p":
        return
    if local_name == "t":
        yield element
        return
    for child in list(element):
        yield from _iter_text_elements_without_nested_paragraphs(child)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _qualified_tag(reference_tag: str, local_name: str) -> str:
    if reference_tag.startswith("{"):
        namespace, _closing, _name = reference_tag[1:].partition("}")
        return f"{{{namespace}}}{local_name}"
    return local_name
