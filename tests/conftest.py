"""Shared pytest fixtures for master_of_hwp tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "samples"


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """Root directory containing sample HWP documents."""
    return SAMPLES_DIR


@pytest.fixture(scope="session")
def sample_files(samples_dir: Path) -> list[Path]:
    """Every .hwp / .hwpx file found under samples/."""
    if not samples_dir.exists():
        return []
    return sorted(
        p for p in samples_dir.rglob("*") if p.suffix.lower() in {".hwp", ".hwpx"}
    )


@pytest.fixture
def tmp_hwpx(tmp_path: Path) -> Iterator[Path]:
    """A minimal fake .hwpx byte blob for fast unit tests.

    The content is not a valid HWPX — it is only a placeholder the Core
    API can treat opaquely for format-classification tests.
    """
    path = tmp_path / "fake.hwpx"
    path.write_bytes(b"PK\x03\x04fake-hwpx-placeholder")
    yield path
