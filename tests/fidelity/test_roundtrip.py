"""Round-trip fidelity benchmarks.

Phase 0 verifies the weakest-but-trivially-true invariant: reading the
same file twice yields identical bytes. As the save path lands in
Phase 1, these tests will begin exercising real round trips and the
expected pass rate will drop — at which point failures become
actionable feedback on save fidelity.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from master_of_hwp.fidelity import FidelityReport, measure_roundtrip


@pytest.mark.fidelity
class TestRoundtrip:
    def test_samples_directory_discovers_files(self, sample_files: list[Path]) -> None:
        if not sample_files:
            pytest.skip("No sample HWP/HWPX files available")
        assert all(p.suffix.lower() in {".hwp", ".hwpx"} for p in sample_files)

    def test_every_sample_roundtrips_byte_equal(self, sample_files: list[Path]) -> None:
        if not sample_files:
            pytest.skip("No sample HWP/HWPX files available")
        reports = [measure_roundtrip(p) for p in sample_files]
        failures = [r for r in reports if not r.byte_equal]
        assert not failures, (
            f"{len(failures)}/{len(reports)} samples failed byte-equal roundtrip"
        )

    def test_report_score_is_one_on_byte_equality(self, tmp_hwpx: Path) -> None:
        report = measure_roundtrip(tmp_hwpx)
        assert isinstance(report, FidelityReport)
        assert report.byte_equal
        assert report.score == pytest.approx(1.0)
        assert report.passed
