# master-of-hwp

Read Korean HWP/HWPX documents in Python, with paragraph editing for HWPX and an API designed for AI workflows.

`master-of-hwp` is a Python-first library for opening real `.hwp` and `.hwpx` files, inspecting sections, paragraphs, and tables, and performing immutable paragraph replacement where the underlying adapter supports it. Version `0.1.0` focuses on a dependable read path plus an initial write primitive for HWPX.

## 30-Second Quickstart

```bash
pip install master-of-hwp
```

```python
from pathlib import Path

from master_of_hwp import HwpDocument

doc = HwpDocument.open("samples/public-official/table-vpos-01.hwpx")
print(doc.sections_count)
first_paragraph = next(
    text
    for paragraphs in doc.section_paragraphs
    for text in paragraphs
    if text
)
print(first_paragraph)

edited = doc.replace_paragraph(0, 0, "PyPI quickstart paragraph")
Path("outputs/quickstart-edited.hwpx").write_bytes(edited.raw_bytes)
```

## API at a Glance

| API | What it does |
| --- | --- |
| `HwpDocument.open(path)` | Open a `.hwp` or `.hwpx` file into an immutable document object |
| `HwpDocument.sections_count` | Count sections |
| `HwpDocument.section_texts` | Read plain text per section |
| `HwpDocument.section_paragraphs` | Read paragraphs per section |
| `HwpDocument.section_tables` | Read nested table data |
| `HwpDocument.replace_paragraph(...)` | Return a new document with one paragraph replaced |

## Supported Formats

| Capability | HWP 5.0 (`.hwp`) | HWPX (`.hwpx`) |
| --- | --- | --- |
| Open document | Yes | Yes |
| Count sections | Yes | Yes |
| Extract section text | Yes | Yes |
| Enumerate paragraphs | Yes | Yes |
| Enumerate tables | Best effort | Yes |
| Replace paragraph | Same-text no-op only | Yes |

## Quickstart Notes

- `replace_paragraph` is a pure function: the original `HwpDocument` stays unchanged.
- HWPX paragraph replacement rewrites the ZIP package in memory and returns new bytes.
- HWP 5.0 write support is intentionally partial in `0.1.0` and will expand in `0.2`.

## Examples

```bash
python examples/01_read_sections.py samples/public-official/table-vpos-01.hwpx
python examples/02_extract_tables.py samples/public-official/table-vpos-01.hwpx
python examples/03_edit_paragraph.py samples/public-official/table-vpos-01.hwpx outputs/edited.hwpx
```

## Roadmap

- `v0.1` — Read path for HWP/HWPX, HWPX paragraph replacement, fidelity helpers
- `v0.2` — Broader write path: insert/delete operations and stronger HWP 5.0 editing support
- `v0.3` — AI-oriented editing loop and provider abstractions

Longer project direction lives in [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Maintainer Release Notes

- The repository includes `.github/workflows/release.yml` for PyPI Trusted Publishing on `v*.*.*` tags.
- PyPI project creation, Trusted Publisher registration, and release tagging are manual maintainer steps.
- Validate a release locally with `python -m build` and `python -m twine check dist/*` before tagging.

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, test expectations, and project scope.

## License

MIT. See [LICENSE](LICENSE).

## Korean README

For the original Korean project overview, see [README.ko.md](README.ko.md).
