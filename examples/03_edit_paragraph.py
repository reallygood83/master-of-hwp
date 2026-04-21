#!/usr/bin/env python3
"""Replace one paragraph in a document and write the edited bytes to disk."""

from __future__ import annotations

import argparse
from pathlib import Path

from master_of_hwp import HwpDocument


def main() -> int:
    """Run the paragraph replacement example."""
    args = _parse_args()
    document = HwpDocument.open(args.input_path)
    edited = document.replace_paragraph(args.section_index, args.paragraph_index, args.new_text)
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_bytes(edited.raw_bytes)
    print(f"wrote {args.output_path}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_path", type=Path, help="Source .hwp or .hwpx file.")
    parser.add_argument("output_path", type=Path, help="Where to write the edited file.")
    parser.add_argument(
        "--section-index",
        type=int,
        default=0,
        help="Zero-based section index to edit.",
    )
    parser.add_argument(
        "--paragraph-index",
        type=int,
        default=0,
        help="Zero-based paragraph index within the section.",
    )
    parser.add_argument(
        "--new-text",
        default="Edited from examples/03_edit_paragraph.py",
        help="Replacement paragraph text.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
