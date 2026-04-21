---
id: 010
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: Natural-Language Edit Loop

## Verification

- `.venv/bin/pytest tests/unit/test_ai_skeleton.py tests/unit/test_intent.py tests/integration/test_ai_edit.py -q` → `23 passed, 1 skipped`
- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed
- `.venv/bin/mypy master_of_hwp` → passed
- `.venv/bin/pytest tests/ -q` → `97 passed, 1 skipped, 1 xfailed`

## Summary

- Added `master_of_hwp.ai.providers` with `LLMProvider` and lazy `AnthropicProvider`
- Added `parse_intent_llm` with rule-based fallback
- Implemented `locate_targets` using `HwpDocument.find_paragraphs`
- Added `AIEditResult` and `HwpDocument.ai_edit`
- Added `ai` optional dependency extra for `anthropic`
- Rule-based no-key path supports quoted replacement requests
- Anthropic integration test skips when `ANTHROPIC_API_KEY` is absent

## Review Focus

- Confirm `dry_run=True` returning `status="refused"` is acceptable, since the current status vocabulary has no `planned`.
- Confirm the rule-based parser's quoted replacement grammar is sufficient for the no-key v0.3 path.
- Confirm `ai_edit` should currently support paragraph replacement only and refuse table-cell/update/insert/delete intents.
