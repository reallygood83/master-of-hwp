"""Round-trip fidelity benchmark: open -> save -> re-open -> compare.

A FidelityReport captures three complementary views:
    * byte_equal: exact byte-level equality (strictest)
    * structural_equal: document tree equality (what matters semantically)
    * text_equal: extracted text equality (what matters to users)

Phase 0 wires the scaffold; byte_equal is implemented. structural_equal
and text_equal return None until the parse pipeline lands in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from master_of_hwp.core.document import HwpDocument


@dataclass(frozen=True)
class FidelityReport:
    """Result of a round-trip fidelity measurement.

    Attributes:
        path: The document path tested.
        byte_equal: True if the round-tripped bytes match exactly.
        byte_diff_count: Number of differing bytes (0 when byte_equal).
        structural_equal: True if the structural parse matches. None
            until the parse pipeline lands.
        text_equal: True if extracted plain text matches. None until
            extraction lands.
        score: Composite score in [0.0, 1.0]. 1.0 = perfect round trip.
    """

    path: Path
    byte_equal: bool
    byte_diff_count: int
    structural_equal: bool | None
    text_equal: bool | None
    score: float

    @property
    def passed(self) -> bool:
        """A report passes when byte OR structural equality holds."""
        return self.byte_equal or self.structural_equal is True


def measure_roundtrip(path: str | Path) -> FidelityReport:
    """Open the document, 'save' it (currently a no-op), re-open, and compare.

    Phase 0: since no save path exists yet, this verifies that opening
    twice returns identical bytes — a weaker but still useful invariant.
    Phase 1 replaces the simulated save with a real save path.

    Args:
        path: Path to a HWP/HWPX file.

    Returns:
        A FidelityReport describing how well the round trip held up.
    """
    doc_a = HwpDocument.open(path)
    doc_b = HwpDocument.open(path)

    byte_equal = doc_a.raw_bytes == doc_b.raw_bytes
    byte_diff_count = 0 if byte_equal else _count_byte_diffs(doc_a.raw_bytes, doc_b.raw_bytes)

    score = 1.0 if byte_equal else max(0.0, 1.0 - byte_diff_count / max(len(doc_a.raw_bytes), 1))

    return FidelityReport(
        path=doc_a.path,
        byte_equal=byte_equal,
        byte_diff_count=byte_diff_count,
        structural_equal=None,
        text_equal=None,
        score=score,
    )


def _count_byte_diffs(a: bytes, b: bytes) -> int:
    """Count positions where two byte sequences differ (length delta included)."""
    common = min(len(a), len(b))
    diffs = sum(1 for i in range(common) if a[i] != b[i])
    diffs += abs(len(a) - len(b))
    return diffs
