"""Tests for the master-of-hwp-studio CLI and bundled resources."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from click.testing import CliRunner
from master_of_hwp_studio.cli import main
from master_of_hwp_studio.mcp import server


def test_cli_help() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "studio" in result.output
    assert "mcp-config" in result.output


def test_mcp_tools_import() -> None:
    assert server.mcp is not None
    assert server.open_document is not None
    assert server.find_paragraphs is not None
    assert server.replace_paragraph is not None


def test_mcp_open_document_tool() -> None:
    sample = (
        Path(__file__).resolve().parents[2] / "samples" / "public-official" / "table-vpos-01.hwpx"
    )
    summary = server.open_document(str(sample))
    assert summary["sections_count"] == 1
    assert summary["paragraph_count"] >= 1


def test_web_assets_bundled() -> None:
    index = resources.files("master_of_hwp_studio.web").joinpath("index.html")
    assert index.read_text(encoding="utf-8").startswith("<!doctype html>")
