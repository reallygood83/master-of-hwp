from __future__ import annotations

from typing import Iterable, Sequence


def build_contextual_selection_prompt(
    *,
    task_type: str,
    instruction: str,
    selected_text: str,
    document_title: str = "",
    previous_paragraphs: Sequence[str] = (),
    following_paragraphs: Sequence[str] = (),
) -> str:
    safe_instruction = instruction.strip() or "선택한 부분을 더 명확하고 자연스럽게 다듬어줘."
    if task_type == "summarize":
        task_label = "summarize"
        format_hint = "선택 영역의 핵심을 3~5문장으로 요약한다. 주변 맥락을 참고하되 결과물은 선택 영역만 치환한다."
    elif task_type == "insert":
        task_label = "insert"
        format_hint = "선택 영역 뒤에 들어갈 새 문단 하나를 작성한다. 문서 전체 톤과 바로 앞뒤 문단의 흐름을 이어야 한다."
    else:
        task_label = "rewrite"
        format_hint = "선택 영역을 같은 의미로 더 좋은 문장으로 다시 쓴다. 문서 전체 톤과 바로 앞뒤 문단의 흐름을 유지해야 한다."

    def render_block(lines: Sequence[str]) -> str:
        cleaned = [ln.strip() for ln in lines if ln and ln.strip()]
        return "\n".join(cleaned) if cleaned else "(없음)"

    title_line = document_title.strip() or "(제목 없음)"
    prev_block = render_block(previous_paragraphs)
    next_block = render_block(following_paragraphs)

    return f'''You are assisting a Korean HWP document editing workflow.
The user has selected a fragment inside a larger document and wants you to operate on ONLY that fragment,
but your answer MUST respect the surrounding context (tone, terminology, numbering, formality).

Return ONLY valid JSON.

Required JSON shape (TWO options):

Option A — plain text replacement:
{{
  "task_type": "{task_label}",
  "content_type": "text",
  "title": "very short label",
  "preview": "human-readable short explanation",
  "content": "final Korean text that will REPLACE the selected fragment"
}}

Option B — HWP table replacement (MUST use when the instruction asks for 표/table/matrix/비교표/일정표 etc.):
{{
  "task_type": "{task_label}",
  "content_type": "table",
  "title": "very short label",
  "preview": "human-readable short explanation",
  "table": {{
    "rows": <int>,
    "cols": <int>,
    "cells": [["r0c0","r0c1",...], ["r1c0","r1c1",...], ...]
  }}
}}

Rules:
- Output must be a single JSON object and nothing else.
- Keep the response in Korean.
- CRITICAL — When the user's instruction mentions ANY of: 표/테이블/table/matrix/행/열/cell/셀/일정표/비교표/정리표/요약표/양식/"표 형식"/"표로"/"표 형태"/"표 모양"/"표로 정리"/"표로 만들"/"표로 바꿔"/"표로 작성"/"이해하기 쉽게 표"/"한눈에 보기"/"깔끔하게 정리", you MUST use Option B (content_type: "table"). DO NOT return Option A with markdown pipes (`|`, `---`) — that is forbidden.
- NEVER embed markdown tables (pipe-separated) inside Option A content. If tabular data is appropriate, always switch to Option B.
- For Option B: cells.length === rows AND every row.length === cols. First row is usually headers.
- For Option B: each cell must be a plain string (no markdown syntax, no pipes, no newlines, no hyphens-only separators).
- For Option A: content must not be empty and must be drop-in replacement for the selected fragment only.
- Do NOT repeat the surrounding context in the output; only produce the replacement.
- Preserve proper nouns, numbers, units, and list numbering from the selection unless the instruction asks otherwise.
- Match the document's overall tone (formal/공문서/보고서 etc.) inferred from the context below.
- title must be under 30 characters. preview must be one short sentence.
- {format_hint}

Document title:
{title_line}

Previous paragraphs (context BEFORE the selection):
"""
{prev_block}
"""

### SELECTED FRAGMENT (operate on this) ###
"""
{selected_text}
"""

Following paragraphs (context AFTER the selection):
"""
{next_block}
"""

User instruction:
{safe_instruction}
'''


def build_paragraph_ai_prompt(*, task_type: str, instruction: str, paragraph_text: str) -> str:
    safe_instruction = instruction.strip() or "문단을 더 명확하고 자연스럽게 다듬어줘."
    if task_type == "summarize":
        task_label = "summarize"
        format_hint = "핵심을 3~5문장으로 요약한다."
    elif task_type == "insert":
        task_label = "insert"
        format_hint = "현재 문단 뒤에 들어갈 새 문단 하나를 작성한다."
    else:
        task_label = "rewrite"
        format_hint = "현재 문단을 같은 의미로 더 좋은 문장으로 다시 쓴다."

    return f'''You are assisting a Korean HWP document editing workflow.
Return ONLY valid JSON.

Required JSON shape:
{{
  "task_type": "{task_label}",
  "title": "very short label",
  "preview": "human-readable short explanation",
  "content": "final Korean text only"
}}

Rules:
- Output must be a single JSON object and nothing else.
- Keep the response in Korean.
- content must not be empty.
- title must be under 30 characters.
- preview must be one short sentence.
- {format_hint}

User instruction:
{safe_instruction}

Current paragraph:
"""
{paragraph_text}
"""
'''


def build_document_ai_prompt(
    *,
    task_type: str,
    instruction: str,
    paragraphs: Iterable[str],
) -> str:
    safe_instruction = instruction.strip() or "문서 전체를 더 명확하고 자연스럽게 다듬어줘."
    if task_type == "summarize":
        task_label = "summarize"
        task_hint = "문서 전체의 핵심을 반영하도록 필요한 문단을 요약·통합한다."
    elif task_type == "append":
        task_label = "append"
        task_hint = "기존 문단은 수정하지 않고, 문서 끝에 이어질 새 문단들을 추가한다 (append 항목에 포함)."
    else:
        task_label = "rewrite"
        task_hint = "문서의 톤과 맥락을 유지하며 문단들을 더 완성도 높은 한국어 문장으로 다시 쓴다."

    numbered_lines: list[str] = []
    for idx, text in enumerate(paragraphs):
        safe_text = (text or "").replace("\n", " ").strip()
        numbered_lines.append(f"[{idx}] {safe_text}")
    numbered_block = "\n".join(numbered_lines) if numbered_lines else "[0] (문서에 문단이 없습니다)"

    return f'''You are assisting a Korean HWP document-wide editing workflow.
Return ONLY valid JSON.

Required JSON shape:
{{
  "task_type": "{task_label}",
  "title": "short label (<=30 chars)",
  "preview": "one short Korean sentence summarizing the changes",
  "edits": [
    {{ "paragraph_index": <int>, "new_text": "수정된 문단 텍스트" }}
  ],
  "appends": [
    "문서 뒤에 새로 추가할 문단 1",
    "문서 뒤에 새로 추가할 문단 2"
  ]
}}

Rules:
- Output must be a single JSON object and nothing else.
- Keep all text in Korean.
- paragraph_index must be one of the indexes shown below (0-based).
- Include only the paragraphs you actually change inside "edits"; unchanged paragraphs must be omitted.
- new_text must be a non-empty single string (use \\n for line breaks if absolutely needed).
- Use "appends" only if the instruction asks to add new paragraphs; otherwise return an empty array.
- {task_hint}

User instruction:
{safe_instruction}

Document paragraphs (0-based index):
"""
{numbered_block}
"""
'''
