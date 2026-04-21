# master-of-hwp

[![PyPI version](https://img.shields.io/pypi/v/master-of-hwp.svg)](https://pypi.org/project/master-of-hwp/)
[![Python](https://img.shields.io/pypi/pyversions/master-of-hwp.svg)](https://pypi.org/project/master-of-hwp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-84%20passed-brightgreen.svg)](#)

> Read Korean HWP/HWPX documents in Python, edit paragraphs in HWPX, and expose structure to AI workflows.

`master-of-hwp` is a Python-first library for opening real `.hwp` and `.hwpx` files, inspecting sections / paragraphs / tables, querying content, and performing immutable paragraph edits. The API is designed to be LLM-friendly: results are plain Python data structures, every mutation returns a new document, and a round-trip fidelity harness validates that edits preserve document structure.

## Why this exists

Korean government, education, and enterprise workflows rely on HWP documents. Most AI tooling can't touch them directly — they get round-tripped through DOCX, shredding tables and formatting. `master-of-hwp` reads the real format, exposes the structure AI needs, and keeps edits byte-level honest.

## 30-Second Quickstart

```bash
pip install master-of-hwp
```

```python
from master_of_hwp import HwpDocument

doc = HwpDocument.open("report.hwpx")

# Inspect
print(f"{doc.sections_count} sections, {len(list(doc.iter_paragraphs()))} paragraphs")
print(doc.summary())

# Query
for section, paragraph, text in doc.find_paragraphs("보도자료"):
    print(f"§{section}.{paragraph}: {text}")

# Edit (HWPX) — immutable: returns a new document
edited = doc.replace_paragraph(0, 0, "New intro text")
edited.path.with_suffix(".edited.hwpx").write_bytes(edited.raw_bytes)
```

## API at a Glance

| API | Purpose |
| --- | --- |
| `HwpDocument.open(path)` | Open `.hwp` / `.hwpx` as an immutable document |
| `.sections_count` | Number of sections |
| `.byte_size` | Size of raw bytes |
| `.section_texts` | Plain text per section |
| `.section_paragraphs` | Paragraphs per section (nested list) |
| `.section_tables` | Tables: `[section][table][row][cell][paragraph]` |
| `.plain_text` | All sections concatenated, format-agnostic normalization |
| `.iter_paragraphs()` | Yield `(section, paragraph, text)` tuples |
| `.find_paragraphs(query, regex=, case_sensitive=)` | Substring or regex search |
| `.summary()` | Compact JSON-serializable overview for LLM context |
| `.replace_paragraph(s, p, text)` | Return a new document with one paragraph replaced |

## Supported Formats

| Capability | HWP 5.0 (`.hwp`) | HWPX (`.hwpx`) |
| --- | --- | --- |
| Open document | ✅ | ✅ |
| Count sections | ✅ | ✅ |
| Extract section text | ✅ | ✅ |
| Enumerate paragraphs | ✅ | ✅ |
| Enumerate tables | Best effort* | ✅ |
| Replace paragraph | Same-length only** | ✅ |
| Insert / delete | ❌ (v0.2) | ❌ (v0.2) |

<sup>* Minimal heuristic anchored on the `TABLE(0x5B)` record; exact row/cell recovery is pending a richer record-level parser.</sup>
<sup>** Different-length HWP 5.0 edits require a CFBF stream resize writer, scheduled for v0.2.</sup>

## AI Integration (v0.3 preview)

The `master_of_hwp.ai` package reserves a frozen public surface for agentic edit loops:

```python
from master_of_hwp.ai import (
    EditIntent, parse_edit_intent,
    ParagraphLocator, LocatorScope,
    ReplaceOperation,  # live in v0.1
    InsertOperation, DeleteOperation,  # NotImplementedError until v0.2
    RollbackTransaction,
)
```

The shapes are stable; runtime implementations of `locate_targets()` and transactional `RollbackTransaction.apply()` land in v0.3.

## Fidelity Harness

```python
from master_of_hwp.fidelity.harness import verify_replace_roundtrip
from master_of_hwp.core.document import SourceFormat

report = verify_replace_roundtrip(
    raw_bytes, SourceFormat.HWPX, section_index=0, paragraph_index=5, new_text="New content"
)
assert report.structural_equal
assert report.edited_paragraph_applied
```

## Examples

```bash
python examples/01_read_sections.py  samples/public-official/table-vpos-01.hwpx
python examples/02_extract_tables.py samples/public-official/table-vpos-01.hwpx
python examples/03_edit_paragraph.py samples/public-official/table-vpos-01.hwpx outputs/edited.hwpx
```

## Roadmap

- **v0.1** ✅ — Read path, HWPX paragraph replacement, fidelity harness, AI scaffold
- **v0.2** — HWP 5.0 resize writer, paragraph insert/delete, table cell edit
- **v0.3** — Full agentic edit loop (intent → locate → operate → verify → rollback)
- **v1.0** — API compatibility contract starts

Details: [docs/ROADMAP.md](docs/ROADMAP.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Philosophy

- **Platform-first** — infrastructure, not a template app.
- **Round-trip fidelity is the contract** — opening and saving must not corrupt structure; proved by a benchmark, not a hope.
- **Agentic document intelligence** — documents should understand themselves.
- **Solo OSS · no commercial pressure · quality first** — take the time it needs.

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, test expectations, and scope.

## License

MIT — see [LICENSE](LICENSE).

## 한국어 개요

프로젝트의 한국어 소개는 [README.ko.md](README.ko.md) 를 참고하세요.
