<div align="center">

# master-of-hwp

[![PyPI](https://img.shields.io/pypi/v/master-of-hwp.svg?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/master-of-hwp/)
[![Studio](https://img.shields.io/pypi/v/master-of-hwp-studio.svg?label=studio&style=for-the-badge&logo=pypi&logoColor=white&color=7c3aed)](https://pypi.org/project/master-of-hwp-studio/)
[![Python](https://img.shields.io/pypi/pyversions/master-of-hwp.svg?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/master-of-hwp/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<a href="https://www.youtube.com/@%EB%B0%B0%EC%9B%80%EC%9D%98%EB%8B%AC%EC%9D%B8-p5v" target="_blank">
  <img src="https://img.shields.io/badge/YouTube-배움의_달인-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube" />
</a>
&nbsp;
<a href="https://x.com/reallygood83" target="_blank">
  <img src="https://img.shields.io/badge/X-@reallygood83-000000?style=for-the-badge&logo=x&logoColor=white" alt="X" />
</a>

**[한국어 (Korean — default)](README.md)**

</div>

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
| `.replace_table_cell_paragraph(s, t, r, c, p, text)` | Edit a paragraph inside a table cell (HWPX) |
| `.ai_edit(request, provider=, dry_run=)` | Natural-language edit pipeline (intent → locate → apply → verify) |

## Supported Formats

| Capability | HWP 5.0 (`.hwp`) | HWPX (`.hwpx`) |
| --- | --- | --- |
| Open document | ✅ | ✅ |
| Count sections | ✅ | ✅ |
| Extract section text | ✅ | ✅ |
| Enumerate paragraphs | ✅ | ✅ |
| Enumerate tables | Best effort* | ✅ |
| Replace paragraph | Same-length only** | ✅ |
| Replace table cell paragraph | ❌ (v0.3) | ✅ |
| Insert / delete | ❌ (v0.3) | ❌ (v0.3) |

<sup>* Minimal heuristic anchored on the `TABLE(0x5B)` record; exact row/cell recovery is pending a richer record-level parser.</sup>
<sup>** Different-length HWP 5.0 edits require a CFBF stream resize writer, scheduled for v0.3.</sup>

## Natural-Language Editing

```bash
pip install master-of-hwp[ai]  # adds anthropic SDK
export ANTHROPIC_API_KEY=sk-ant-...
```

```python
from master_of_hwp import HwpDocument
from master_of_hwp.ai.providers import AnthropicProvider

doc = HwpDocument.open("가정통신문.hwpx")
result = doc.ai_edit(
    "첫 번째 문단의 '급식비'를 '수업료'로 바꿔줘",
    provider=AnthropicProvider(),
)
if result.status == "applied":
    result.new_doc.path.with_suffix(".edited.hwpx").write_bytes(result.new_doc.raw_bytes)
else:
    print(result.message)  # refused / failed explanation
```

Without an API key, a rule-based fallback parser handles simple patterns
(`바꿔`, `변경`, keyword matches). See `master_of_hwp.ai.providers` for
the `LLMProvider` Protocol — plug in OpenAI, local Ollama, etc.

## Studio (Non-developer GUI)

For teachers / office workers who want a one-click experience — **rhwp WYSIWYG editor is now bundled** (v0.2+):

```bash
pip install master-of-hwp-studio
mohwp studio                    # launches web GUI + MCP server + bundled rhwp editor
mohwp mcp-config                # prints Claude Desktop config snippet
```

No Node.js setup required. The rhwp editor runs automatically on `localhost:7700`.

See [`studio/README.md`](studio/README.md).

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

**Contributions are very welcome** — this is an open, community-driven project.

- 🐛 **Bug reports / feature requests:** [open an issue](https://github.com/reallygood83/master-of-hwp/issues)
- 💻 **Code contributions:** fork → branch → PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, test expectations, and scope.
- 💬 **Questions / discussion:** [GitHub Discussions](https://github.com/reallygood83/master-of-hwp/discussions)

Areas we'd love help on:
- HWP 5.0 CFBF resize writer (v0.3)
- Paragraph insert / delete operations for both formats
- Additional LLM providers (OpenAI, Gemini, local Ollama) on top of the `LLMProvider` Protocol
- Windows / Linux installer for `master-of-hwp-studio`
- Accessibility improvements to the web GUI

No contribution is too small. Documentation fixes, typo corrections, and sample HWP files are equally valuable.

## Acknowledgments

The WYSIWYG editor bundled in `master-of-hwp-studio` is built on **[rhwp](https://github.com/edwardkim/rhwp)** by **[@edwardkim](https://github.com/edwardkim)** — a Rust + WebAssembly HWP parsing / rendering engine. This project would not be possible without their work. If you find `master-of-hwp-studio` useful, please star rhwp too.

## License

MIT — see [LICENSE](LICENSE).

## 한국어 (Korean)

The default project README is now in Korean: [README.md](README.md).
