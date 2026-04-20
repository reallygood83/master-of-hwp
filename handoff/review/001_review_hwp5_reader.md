---
id: 001
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: HWP 5.0 Section Counter Spike

## Summary

Codex verified that spike `001` is already implemented in the current branch
and completed the collaboration handoff.

- Confirmed `master_of_hwp/adapters/hwp5_reader.py` exists
- Confirmed `count_sections(raw_bytes: bytes) -> int` and `Hwp5FormatError`
- Confirmed unit tests cover empty bytes, invalid signature, and real sample file
- Confirmed `olefile>=0.47` is declared in `pyproject.toml`

## Verification

- `.venv/bin/pytest tests/ -q` → `30 passed`
- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed

## Review Focus

- Confirm `BodyText/Section*` counting is the right minimal contract for the upcoming `HwpDocument.sections_count` integration.
- Confirm raising `Hwp5FormatError` when no section streams are present is the desired failure mode.
- Check whether `hwp5_reader` should be re-exported from `master_of_hwp.adapters.__init__` before downstream integration.
