---
id: 006
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: Table Enumeration Spike

## Verification

- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed
- `.venv/bin/mypy master_of_hwp` → passed
- `.venv/bin/pytest tests/ -q` → `50 passed`

## Summary

Codex completed spike `006` for per-section table enumeration on both adapters.

- Added `extract_section_tables(raw_bytes)` to `hwp5_reader.py`
- Added `extract_section_tables(raw_bytes)` to `hwpx_reader.py`
- HWP5 uses a minimal `TABLE(0x5B)`-anchored heuristic and materializes one-row/one-cell tables from descendant `PARA_TEXT` records when found
- HWPX walks `tbl > tr > tc`, collects per-cell paragraph lists, and avoids nested-table double counting by stopping recursion once a table node is claimed
- Sections without tables return `[]`
- Unit tests now cover invalid input, HWP5 shape validity, and real HWPX table content

## Review Focus

- Confirm the HWP5 minimal table heuristic is acceptable for this spike before richer record-level table semantics exist.
- Confirm the current HWPX recursion strategy should intentionally skip nested tables rather than enumerate them separately.
- Confirm the chosen nested list shape matches what you want for `HwpDocument.section_tables` integration, since the handoff prose implies a deeper structure than the shorthand type signature.
