---
id: 007
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: Write Path Spike

## Verification

- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed
- `.venv/bin/mypy master_of_hwp` → passed
- `.venv/bin/pytest tests/ -q` → `55 passed, 1 xfailed`

## Deliverable Status

### 1. `replace_paragraph`

- HWPX: **complete for spike scope**
  - `replace_paragraph(raw_bytes, section_index, paragraph_index, new_text) -> bytes`
  - ZIP rebuilt in memory, target section XML rewritten, other entries preserved
  - out-of-range uses `IndexError`
- HWP5: **partial by design**
  - no-op same-text replacement succeeds and preserves bytes
  - non-no-op replacement raises `Hwp5FormatError("...pending richer CFBF writer")`
  - different-length case is covered by an xfail test

### 2. Fidelity Harness

- **complete**
  - Added `master_of_hwp/fidelity/harness.py`
  - `FidelityReport`
  - `verify_identity_roundtrip`
  - `verify_replace_roundtrip`
- Existing `master_of_hwp.fidelity` package now re-exports the new harness APIs while preserving `measure_roundtrip`

### 3. `tests/unit/test_write_path.py`

- **complete for spike scope**
  - HWPX no-op replace roundtrip
  - HWPX shorter replace
  - HWPX longer replace
  - HWPX out-of-range
  - HWP5 same-length no-op
  - HWP5 different-length xfail

## Review Focus

- Confirm the package-level fidelity adaptation is acceptable even though the handoff asked for `master_of_hwp/fidelity.py` and the repo already had a `master_of_hwp/fidelity/` package.
- Confirm HWP5 partial support is sufficient for this spike, since only no-op same-text replacement is live and true in-place stream rewriting is deferred.
- Confirm HWPX paragraph replacement should intentionally collapse multiple `<t>` nodes in the target paragraph down to one text node for now.
