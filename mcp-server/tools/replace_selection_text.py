from __future__ import annotations

from adapters.rhwp_adapter import RHWPAdapter, RHWPAdapterError
from document_store import DOCUMENT_STORE, DocumentStoreError, OperationRecord
from schemas.common import ToolResponseDict, build_tool_response


def replace_selection_text_tool(
    document_id: str,
    paragraph_index: int,
    start_char: int,
    end_char: int,
    new_text: str,
) -> ToolResponseDict:
    resolved_document_id = document_id.strip()
    if not resolved_document_id:
        return build_tool_response(ok=False, error_code="MISSING_DOCUMENT_ID", message="document_id is required.")

    try:
        record = DOCUMENT_STORE.get(resolved_document_id)
    except DocumentStoreError as exc:
        return build_tool_response(ok=False, error_code="UNKNOWN_DOCUMENT_ID", message=str(exc))

    if record["readonly"]:
        return build_tool_response(ok=False, error_code="READONLY_DOCUMENT", message="This document session is readonly.")

    adapter = RHWPAdapter()
    working_text = DOCUMENT_STORE.get_working_text(resolved_document_id)
    if working_text is None:
        try:
            working_text = adapter.extract_text(record["path"]).text
        except RHWPAdapterError as exc:
            return build_tool_response(ok=False, error_code="DOCUMENT_EXTRACTION_FAILED", message=str(exc))

    paragraphs = DOCUMENT_STORE.get_working_paragraphs(resolved_document_id)
    if not paragraphs:
        structure = adapter.extract_structure(str(record["path"]))
        raw_paragraphs = structure.get("paragraphs", []) if isinstance(structure, dict) else []
        paragraphs = []
        if isinstance(raw_paragraphs, list):
            section_counters: dict[int, int] = {}
            for index, item in enumerate(raw_paragraphs):
                if not isinstance(item, dict):
                    continue
                section_index = int(item.get("section_index", 0)) if isinstance(item.get("section_index", 0), int) else 0
                section_para_index = section_counters.get(section_index, 0)
                section_counters[section_index] = section_para_index + 1
                text = str(item.get("text", ""))
                paragraphs.append({
                    "paragraph_index": index,
                    "section_index": section_index,
                    "section_para_index": section_para_index,
                    "text": text,
                    "text_preview": str(item.get("text_preview", text.replace("\n", " ")[:120])),
                    "char_count": int(item.get("char_count", len(text))) if isinstance(item.get("char_count", len(text)), int) else len(text),
                })
        DOCUMENT_STORE.set_working_paragraphs(resolved_document_id, paragraphs)

    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return build_tool_response(ok=False, error_code="INVALID_PARAGRAPH_INDEX", message=f"paragraph_index {paragraph_index} is out of range.")

    paragraph = paragraphs[paragraph_index]
    paragraph_text = str(paragraph["text"])
    if start_char < 0 or end_char < start_char or end_char > len(paragraph_text):
        return build_tool_response(ok=False, error_code="INVALID_SELECTION_RANGE", message="Selection range is out of bounds.")

    updated = paragraph_text[:start_char] + new_text + paragraph_text[end_char:]
    paragraph["text"] = updated
    paragraph["text_preview"] = updated.replace("\n", " ")[:120]
    paragraph["char_count"] = len(updated)
    DOCUMENT_STORE.set_working_paragraphs(resolved_document_id, paragraphs)
    DOCUMENT_STORE.set_working_text(
        resolved_document_id,
        "\n\n".join(str(p["text"]).strip() for p in paragraphs if str(p["text"]).strip()),
    )

    if record["format"] in {"hwp", "hwpx"}:
        op: OperationRecord = {
            "type": "replace_selection_text",
            "section_index": int(paragraph["section_index"]),
            "para_index": int(paragraph["section_para_index"]),
            "start_char": start_char,
            "end_char": end_char,
            "new_text": new_text,
        }
        DOCUMENT_STORE.append_operation(resolved_document_id, op)

    return build_tool_response(
        ok=True,
        message="selection replaced",
        data={
            "document_id": resolved_document_id,
            "paragraph_index": paragraph_index,
            "start_char": start_char,
            "end_char": end_char,
            "new_text_preview": new_text[:120],
        },
    )
