# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-21

### Added

- `HwpDocument.plain_text` — format-agnostic concatenation with HWP 5.0 `\r` → `\n` normalization
- `HwpDocument.iter_paragraphs()` — yields `(section_index, paragraph_index, text)` tuples in document order
- `HwpDocument.find_paragraphs(query, regex=, case_sensitive=)` — substring / regex search
- `HwpDocument.summary()` — JSON-serializable structural overview for AI context
- `HwpDocument.replace_table_cell_paragraph(...)` — HWPX table cell paragraph replacement
- `HwpDocument.ai_edit(natural_language_request, provider=, dry_run=, confidence_threshold=)` — natural-language edit pipeline (intent → locate → apply → verify)
- `master_of_hwp.ai.providers` — `LLMProvider` Protocol + `AnthropicProvider` (lazy import, `pip install master-of-hwp[ai]`)
- `master_of_hwp.ai.intent.parse_intent_llm()` — LLM-backed intent parsing with JSON schema
- `master_of_hwp.ai.locator.locate_targets()` — real implementation (find_paragraphs + LLM re-ranking)
- `AIEditResult` dataclass with `status` / `intent` / `locator` / `new_doc` / `fidelity_report` / `message`
- Hypothesis-based property tests for `replace_paragraph` idempotency and locality

### Changed

- `master_of_hwp.ai` package exports expanded to full pipeline (previously scaffold-only)

### Known Limitations

- HWP 5.0 write path still limited to same-length paragraph replacement (CFBF resize writer pending v0.3)
- Insert / delete paragraph operations not yet available (pending v0.3)
- Table cell editing available for HWPX only; HWP 5.0 raises `NotImplementedError`

## [0.1.0] - 2026-04-21

### Added

- `HwpDocument.open(path)` for `.hwp` and `.hwpx` files
- `HwpDocument.sections_count` to count sections in both formats
- `HwpDocument.section_texts` for plain text per section
- `HwpDocument.section_paragraphs` for paragraph lists per section
- `HwpDocument.section_tables` for nested table data as `[section][table][row][cell][paragraph]`
- `HwpDocument.replace_paragraph(section_index, paragraph_index, new_text)` with full HWPX support and HWP 5.0 same-text no-op support
- `master_of_hwp.fidelity` round-trip fidelity helpers for identity and replace checks
- Strict type hints and mypy-clean API surface on Python 3.11+
- Example scripts for reading sections, extracting tables, and editing a paragraph
- GitHub Actions release workflow for PyPI Trusted Publishing

### Known Limitations

- HWP 5.0 write path does not yet support arbitrary-length paragraph replacement
- Insert and delete paragraph operations are not available yet
- Table cell editing is not available yet
- AI editing loop and provider integration are planned for later releases
