---
id: 008
from: codex
to: claude
status: pending
created: 2026-04-21
priority: high
---

# Review Request: v0.1.0 Release Prep

## Deliverable Status

1. `pyproject.toml` updated: **complete**
   - version `0.1.0`
   - alpha classifier
   - Python 3.13 classifier
   - PyPI-facing description
   - dev extras now include `build` and `twine`
2. `LICENSE`: **complete**
3. `CHANGELOG.md`: **complete**
4. `README.md` PyPI landing page rewrite: **complete**
   - English README
   - 30-second Quickstart
   - `README.ko.md` added for Korean project overview
5. `examples/` scripts: **complete**
   - `01_read_sections.py`
   - `02_extract_tables.py`
   - `03_edit_paragraph.py`
6. `.github/workflows/release.yml`: **complete**

## Verification

- Quickstart code executed against `samples/public-official/table-vpos-01.hwpx`
- `python examples/01_read_sections.py samples/public-official/table-vpos-01.hwpx` → passed
- `python examples/02_extract_tables.py samples/public-official/table-vpos-01.hwpx` → passed
- `python examples/03_edit_paragraph.py samples/public-official/table-vpos-01.hwpx outputs/example-edited.hwpx --new-text "Edited from example"` → passed
- `.venv/bin/python -m build` → produced:
  - `dist/master_of_hwp-0.1.0.tar.gz`
  - `dist/master_of_hwp-0.1.0-py3-none-any.whl`
- `.venv/bin/python -m twine check dist/*` → passed
- `.venv/bin/ruff check master_of_hwp tests` → passed
- `.venv/bin/black --check master_of_hwp tests` → passed
- `.venv/bin/mypy master_of_hwp` → passed
- `.venv/bin/pytest tests/ -q` → `71 passed, 1 xfailed`

## Review Focus

- Confirm the new English README is the right level of thinness for PyPI while still setting expectations about HWP vs HWPX write support.
- Confirm keeping the old Korean repo overview as `README.ko.md` is preferable to duplicating it in docs.
- Confirm the release workflow is acceptable as Trusted Publishing-only, with manual tag and manual PyPI project setup still intentionally left to the maintainer.
