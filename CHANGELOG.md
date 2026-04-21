# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
