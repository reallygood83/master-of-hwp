---
id: 009
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: HWPX Table Cell Edit

## Verification

- `.venv/bin/pytest tests/unit/test_table_cell_write.py tests/integration/test_document_table_edit.py -q` → `9 passed`
- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed
- `.venv/bin/mypy master_of_hwp` → passed
- `.venv/bin/pytest tests/ -q` → `93 passed, 1 xfailed`

## Summary

- Added `replace_table_cell_paragraph` to `master_of_hwp.adapters.hwpx_reader`
- Added `HwpDocument.replace_table_cell_paragraph`
- HWPX table cell replacement follows the existing outer-table read policy
- HWP 5.0 table cell editing raises `NotImplementedError`
- Added unit tests for no-op, mutation, locality, and out-of-range indexes
- Added integration tests for the document method and HWP 5.0 unsupported path

## Review Focus

- Confirm write indexing matches `section_tables[section][table][row][cell][paragraph]`.
- Confirm outer-table-only behavior is the desired v0.2 policy for both read and write.
- Confirm collapsing the target cell paragraph to the existing `_replace_paragraph_text` behavior is acceptable.
