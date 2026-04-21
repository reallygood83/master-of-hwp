#!/usr/bin/env python3
"""Pretty-print table structure for a HWP/HWPX document."""

from __future__ import annotations

import argparse
from pathlib import Path

from master_of_hwp import HwpDocument


def main() -> int:
    """Run the table extraction example."""
    args = _parse_args()
    document = HwpDocument.open(args.path)
    for section_index, tables in enumerate(document.section_tables):
        print(f"[section {section_index}] tables={len(tables)}")
        for table_index, table in enumerate(tables):
            print(f"  [table {table_index}] rows={len(table)}")
            for row_index, row in enumerate(table):
                cell_preview = [" / ".join(cell) for cell in row]
                print(f"    row {row_index}: {cell_preview}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to a .hwp or .hwpx file.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
