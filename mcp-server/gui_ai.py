from __future__ import annotations

from cli_wrappers.claude_wrapper import ClaudeWrapperError, run_claude_json
from orchestration.prompt_builder import build_paragraph_ai_prompt
from orchestration.response_mapper import map_ai_preview
from tools.extract_document_structure import extract_document_structure_tool
from tools.insert_paragraph_after import insert_paragraph_after_tool
from tools.replace_paragraph_text import replace_paragraph_text_tool
from tools.replace_selection_text import replace_selection_text_tool


def ai_preview_tool(document_id: str, paragraph_index: int, task_type: str, instruction: str) -> dict[str, object]:
    structure = extract_document_structure_tool(document_id=document_id)
    if not structure.get("ok"):
        return structure

    data = structure.get("data")
    if not isinstance(data, dict):
        return {
            "ok": False,
            "message": "Document structure payload is invalid.",
            "error_code": "INVALID_STRUCTURE_PAYLOAD",
        }

    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list) or paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return {
            "ok": False,
            "message": f"paragraph_index {paragraph_index} is out of range.",
            "error_code": "INVALID_PARAGRAPH_INDEX",
        }

    paragraph = paragraphs[paragraph_index]
    if not isinstance(paragraph, dict):
        return {
            "ok": False,
            "message": "Paragraph payload is invalid.",
            "error_code": "INVALID_PARAGRAPH_PAYLOAD",
        }
    paragraph_text = str(paragraph.get("text", "")).strip()
    prompt = build_paragraph_ai_prompt(
        task_type=task_type,
        instruction=instruction,
        paragraph_text=paragraph_text,
    )

    try:
        result = run_claude_json(prompt)
    except ClaudeWrapperError as exc:
        return {
            "ok": False,
            "message": str(exc),
            "error_code": "CLAUDE_WRAPPER_FAILED",
        }

    return map_ai_preview(
        task_type=task_type,
        paragraph_index=paragraph_index,
        response=result["structured"],
    )


def ai_selection_preview_tool(selection: dict[str, object], task_type: str, instruction: str) -> dict[str, object]:
    selected_text = str(selection.get("text", "")).strip()
    if not selected_text:
        return {
            "ok": False,
            "message": "선택된 텍스트가 없습니다.",
            "error_code": "EMPTY_SELECTION",
        }

    prompt = build_paragraph_ai_prompt(
        task_type=task_type,
        instruction=instruction,
        paragraph_text=selected_text,
    )

    try:
        result = run_claude_json(prompt)
    except ClaudeWrapperError as exc:
        return {
            "ok": False,
            "message": str(exc),
            "error_code": "CLAUDE_WRAPPER_FAILED",
        }

    mapped = map_ai_preview(
        task_type=task_type,
        paragraph_index=int(selection.get("paragraph_index", 0)),
        response=result["structured"],
    )
    if mapped.get("ok"):
        data = mapped.get("data")
        if isinstance(data, dict):
            data["selection"] = selection
    return mapped


def ai_apply_tool(document_id: str, task_type: str, paragraph_index: int, content: str) -> dict[str, object]:
    if task_type == "insert":
        return insert_paragraph_after_tool(
            document_id=document_id,
            after_paragraph_index=paragraph_index,
            text=content,
        )
    return replace_paragraph_text_tool(
        document_id=document_id,
        paragraph_index=paragraph_index,
        new_text=content,
    )


def ai_apply_selection_tool(document_id: str, selection: dict[str, object], content: str) -> dict[str, object]:
    return replace_selection_text_tool(
        document_id=document_id,
        paragraph_index=int(selection.get("paragraph_index", 0)),
        start_char=int(selection.get("start_char", 0)),
        end_char=int(selection.get("end_char", 0)),
        new_text=content,
    )
