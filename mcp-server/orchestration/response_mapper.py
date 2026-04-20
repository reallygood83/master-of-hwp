from __future__ import annotations

import re

from schemas.common import ToolResponseDict, build_tool_response

MAX_TABLE_ROWS = 50
MAX_TABLE_COLS = 20

# Detects a GitHub-flavored markdown table block: header row + separator + >=1 data row.
# Tolerates leading/trailing pipes and whitespace.
_MD_TABLE_LINE = re.compile(r"^\s*\|?\s*(.+?)\s*\|?\s*$")
_MD_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _split_md_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _extract_markdown_table(text: str) -> dict[str, object] | None:
    """Scan `text` for a markdown table block and return a normalized table dict.

    Returns None if nothing looks like a markdown table.
    """
    if not text or "|" not in text:
        return None
    lines = text.splitlines()
    for start in range(len(lines) - 1):
        header = lines[start]
        sep = lines[start + 1]
        if "|" not in header:
            continue
        if not _MD_SEPARATOR.match(sep):
            continue
        header_cells = _split_md_row(header)
        if len(header_cells) < 2:
            continue
        cols = len(header_cells)
        rows_cells: list[list[str]] = [header_cells]
        cursor = start + 2
        while cursor < len(lines):
            line = lines[cursor]
            if "|" not in line or not line.strip():
                break
            cells = _split_md_row(line)
            if not any(cells):
                break
            # pad / trim to match column count
            if len(cells) < cols:
                cells = cells + [""] * (cols - len(cells))
            elif len(cells) > cols:
                cells = cells[:cols]
            rows_cells.append(cells)
            cursor += 1
        if len(rows_cells) < 2:
            continue
        rows = len(rows_cells)
        if rows > MAX_TABLE_ROWS or cols > MAX_TABLE_COLS:
            continue
        return {"rows": rows, "cols": cols, "cells": rows_cells}
    return None


def _normalize_table(raw: object) -> tuple[dict[str, object] | None, str | None]:
    """Validate and normalize an AI-provided table payload.

    Returns (normalized_table, error_message). On success error_message is None.
    """
    if not isinstance(raw, dict):
        return None, "table payload is not an object"

    try:
        rows = int(raw.get("rows", 0))
        cols = int(raw.get("cols", 0))
    except (TypeError, ValueError):
        return None, "table.rows/cols must be integers"

    cells_raw = raw.get("cells")
    if not isinstance(cells_raw, list) or not cells_raw:
        return None, "table.cells must be a non-empty list"

    if rows <= 0:
        rows = len(cells_raw)
    if cols <= 0 and isinstance(cells_raw[0], list):
        cols = len(cells_raw[0])

    if rows <= 0 or cols <= 0:
        return None, "table.rows and table.cols must be positive"
    if rows > MAX_TABLE_ROWS or cols > MAX_TABLE_COLS:
        return None, f"table exceeds limits ({MAX_TABLE_ROWS}x{MAX_TABLE_COLS})"
    if len(cells_raw) != rows:
        return None, f"cells row count {len(cells_raw)} != rows {rows}"

    normalized_cells: list[list[str]] = []
    for r_idx, row in enumerate(cells_raw):
        if not isinstance(row, list):
            return None, f"cells[{r_idx}] is not a list"
        if len(row) != cols:
            return None, f"cells[{r_idx}] length {len(row)} != cols {cols}"
        normalized_row = [str(cell).replace("\r", " ").replace("\n", " ").strip() for cell in row]
        normalized_cells.append(normalized_row)

    return {"rows": rows, "cols": cols, "cells": normalized_cells}, None


def _build_table_response(
    *,
    task_type: str,
    paragraph_index: int,
    title: str,
    preview: str,
    table: dict[str, object],
) -> ToolResponseDict:
    flat_preview_rows = [" | ".join(row) for row in table["cells"]]  # type: ignore[index]
    fallback_content = "\n".join(flat_preview_rows)
    return build_tool_response(
        ok=True,
        message="ai preview ready (table)",
        data={
            "task_type": task_type,
            "paragraph_index": paragraph_index,
            "title": title,
            "preview": preview,
            "content_type": "table",
            "content": fallback_content,
            "table": table,
        },
    )


def map_ai_preview(*, task_type: str, paragraph_index: int, response: dict[str, object]) -> ToolResponseDict:
    content_type = str(response.get("content_type", "text")).strip().lower() or "text"
    title = str(response.get("title", "AI 결과")).strip() or "AI 결과"
    preview = str(response.get("preview", "")).strip()

    if content_type == "table":
        table, err = _normalize_table(response.get("table"))
        if err or table is None:
            return build_tool_response(
                ok=False,
                error_code="AI_INVALID_TABLE",
                message=f"AI table payload invalid: {err}",
                suggestion="Try a simpler instruction or request a plain text result.",
            )
        return _build_table_response(
            task_type=task_type, paragraph_index=paragraph_index,
            title=title, preview=preview, table=table,
        )

    content = str(response.get("content", "")).strip()
    if not content:
        return build_tool_response(
            ok=False,
            error_code="AI_EMPTY_CONTENT",
            message="AI response did not include usable content.",
            suggestion="Try a simpler instruction or shorter paragraph.",
        )

    # 안전망: LLM이 content_type="text"로 보냈지만 실제로는 markdown 파이프 표를 심어놓은 경우,
    # 후처리로 HWP 네이티브 표로 전환한다. 사용자가 `표 형식/표로` 같은 변형 표현을 썼을 때
    # 프롬프트 트리거가 빗나가더라도 결과적으로 표가 들어가도록 보장.
    md_table = _extract_markdown_table(content)
    if md_table is not None:
        auto_title = title if title != "AI 결과" else "표"
        return _build_table_response(
            task_type=task_type, paragraph_index=paragraph_index,
            title=auto_title,
            preview=preview or "마크다운 표를 HWP 표로 변환했습니다.",
            table=md_table,
        )

    return build_tool_response(
        ok=True,
        message="ai preview ready",
        data={
            "task_type": task_type,
            "paragraph_index": paragraph_index,
            "title": title,
            "preview": preview,
            "content_type": "text",
            "content": content,
        },
    )
