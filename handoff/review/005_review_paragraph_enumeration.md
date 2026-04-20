---
id: 005
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: Paragraph Enumeration Spike

## Verification

- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed
- `.venv/bin/mypy master_of_hwp` → passed
- `.venv/bin/pytest tests/ -q` → `46 passed`

## Summary

Codex completed spike `005` for per-section paragraph enumeration on both adapters.

- Added `extract_section_paragraphs(raw_bytes) -> list[list[str]]` to `hwp5_reader.py`
- Added `extract_section_paragraphs(raw_bytes) -> list[list[str]]` to `hwpx_reader.py`
- HWP5 paragraphs are split per `PARA_TEXT` record and trailing `\r` is removed
- HWPX paragraphs are split per `<p>` element and empty paragraphs remain `""`
- Outer list length stays aligned with `count_sections(raw_bytes)` in both adapters
- Added unit tests that tie paragraph enumeration back to existing section-text behavior

## Review Focus

- Confirm the HWP5 normalization rule of trimming only trailing `\r` is the right minimal contract before richer paragraph metadata exists.
- Confirm preserving empty HWPX paragraphs as `""` is the correct shape for the upcoming `HwpDocument.section_paragraphs` property.
- Confirm using `extract_section_paragraphs` as the source of truth for HWPX text extraction is the desired layering for future edits.
