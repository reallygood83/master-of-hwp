#!/usr/bin/env python3
"""Print section and paragraph summaries for a HWP/HWPX document."""

from __future__ import annotations

import argparse
from pathlib import Path

from master_of_hwp import HwpDocument


def main() -> int:
    """Run the section-reading example."""
    args = _parse_args()
    document = HwpDocument.open(args.path)
    print(f"format={document.source_format} sections={document.sections_count}")
    for section_index, paragraphs in enumerate(document.section_paragraphs):
        print(f"[section {section_index}] paragraphs={len(paragraphs)}")
        for paragraph_index, paragraph in enumerate(paragraphs):
            if paragraph:
                print(f"  {section_index}.{paragraph_index}: {paragraph}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to a .hwp or .hwpx file.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
