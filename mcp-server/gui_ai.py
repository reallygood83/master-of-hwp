from __future__ import annotations

from pathlib import Path

from cli_wrappers import ProviderRouterError, run_provider_json
from orchestration.prompt_builder import (
    build_contextual_selection_prompt,
    build_paragraph_ai_prompt,
)
from orchestration.response_mapper import map_ai_preview
from tools.extract_document_structure import extract_document_structure_tool
from tools.insert_paragraph_after import insert_paragraph_after_tool
from tools.replace_paragraph_text import replace_paragraph_text_tool
from tools.replace_selection_text import replace_selection_text_tool

CONTEXT_WINDOW_BEFORE = 6
CONTEXT_WINDOW_AFTER = 4
CONTEXT_CHAR_BUDGET = 1800


def _trim_context(paragraphs: list[str], limit: int) -> list[str]:
    """Trim from the far end until total char count fits the budget."""
    total = sum(len(p) for p in paragraphs)
    trimmed = list(paragraphs)
    while trimmed and total > limit:
        removed = trimmed.pop(0)
        total -= len(removed)
    return trimmed


def _gather_selection_context(
    document_id: str, selection: dict[str, object]
) -> tuple[str, list[str], list[str]]:
    """Return (document_title, previous_paragraphs, following_paragraphs)."""
    if not document_id:
        return "", [], []
    structure = extract_document_structure_tool(document_id=document_id)
    if not structure.get("ok"):
        return "", [], []
    data = structure.get("data")
    if not isinstance(data, dict):
        return "", [], []
    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list):
        return "", [], []

    title = str(data.get("path") or data.get("file_name") or "")
    if title:
        title = Path(title).name

    start = selection.get("start") if isinstance(selection.get("start"), dict) else {}
    end = selection.get("end") if isinstance(selection.get("end"), dict) else {}
    start_idx = int(start.get("paragraphIndex", selection.get("paragraph_index", 0)) or 0)
    end_idx = int(end.get("paragraphIndex", start_idx) or start_idx)

    def _text_at(i: int) -> str:
        if 0 <= i < len(paragraphs) and isinstance(paragraphs[i], dict):
            return str(paragraphs[i].get("text", "")).strip()
        return ""

    prev_paragraphs = [
        _text_at(i)
        for i in range(max(0, start_idx - CONTEXT_WINDOW_BEFORE), start_idx)
    ]
    next_paragraphs = [
        _text_at(i)
        for i in range(end_idx + 1, min(len(paragraphs), end_idx + 1 + CONTEXT_WINDOW_AFTER))
    ]
    # Split budget roughly 60/40 between before/after
    prev_paragraphs = _trim_context(prev_paragraphs, int(CONTEXT_CHAR_BUDGET * 0.6))
    next_paragraphs = _trim_context(list(reversed(next_paragraphs)), int(CONTEXT_CHAR_BUDGET * 0.4))
    next_paragraphs = list(reversed(next_paragraphs))
    return title, prev_paragraphs, next_paragraphs


def ai_preview_tool(provider: str, document_id: str, paragraph_index: int, task_type: str, instruction: str) -> dict[str, object]:
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
        result = run_provider_json(provider, prompt, workdir='/Users/moon/Desktop/master-of-hwp')
    except ProviderRouterError as exc:
        return {
            "ok": False,
            "message": str(exc),
            "error_code": f"{provider.upper()}_WRAPPER_FAILED",
        }

    mapped = map_ai_preview(
        task_type=task_type,
        paragraph_index=paragraph_index,
        response=result["structured"],
    )
    if mapped.get('ok'):
        data = mapped.get('data')
        if isinstance(data, dict):
            data['provider'] = result['provider']
    return mapped


def ai_selection_preview_tool(
    provider: str,
    selection: dict[str, object],
    task_type: str,
    instruction: str,
    document_id: str = "",
) -> dict[str, object]:
    selected_text = str(selection.get("text", "")).strip()
    if not selected_text:
        return {
            "ok": False,
            "message": "선택된 텍스트가 없습니다.",
            "error_code": "EMPTY_SELECTION",
        }

    title, prev_paragraphs, next_paragraphs = _gather_selection_context(
        document_id=document_id, selection=selection
    )

    prompt = build_contextual_selection_prompt(
        task_type=task_type,
        instruction=instruction,
        selected_text=selected_text,
        document_title=title,
        previous_paragraphs=prev_paragraphs,
        following_paragraphs=next_paragraphs,
    )

    try:
        result = run_provider_json(provider, prompt, workdir='/Users/moon/Desktop/master-of-hwp')
    except ProviderRouterError as exc:
        return {
            "ok": False,
            "message": str(exc),
            "error_code": f"{provider.upper()}_WRAPPER_FAILED",
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
            data['provider'] = result['provider']
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
