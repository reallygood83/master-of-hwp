"""Round-trip fidelity measurement.

The central contract of master-of-hwp: opening a document and saving
it without edits must produce a structurally equivalent result. This
package measures how well we uphold that contract.
"""

from master_of_hwp.fidelity.roundtrip import FidelityReport, measure_roundtrip

__all__ = ["FidelityReport", "measure_roundtrip"]
