---
id: 003
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: HWP 5.0 Section Text Extractor Spike

## Summary

Codex completed spike `003` for minimal HWP 5.0 section text extraction.

- Added `extract_section_texts(raw_bytes: bytes) -> list[str]` to `master_of_hwp/adapters/hwp5_reader.py`
- Reused `Hwp5FormatError` for invalid compound files, bad deflate streams, and malformed records
- Added raw-DEFLATE decompression, HWP record iteration, and `PARA_TEXT` (`0x43`) decoding
- Stripped HWP control blocks while preserving printable text and paragraph breaks
- Preserved the invariant `len(extract_section_texts(raw_bytes)) == count_sections(raw_bytes)`
- Added unit tests for invalid input reuse and real sample extraction

## Verification

- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed
- `.venv/bin/mypy master_of_hwp` → passed
- `.venv/bin/pytest tests/ -q` → `38 passed`

## Review Focus

- Confirm the current control-block skipping heuristic is acceptable for the spike before a fuller HWP text model exists.
- Confirm preserving `\r` paragraph separators in extracted text matches the expected downstream plain-text contract.
- Confirm keeping the work scoped to `hwp5_reader.py` and its unit tests remains the right boundary for this spike.
