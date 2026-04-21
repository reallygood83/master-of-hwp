"""Integration tests for the Studio HTTP API endpoints.

Starts the HTTP server on an ephemeral port and exercises each
endpoint via http.client. Uses the real `master_of_hwp` Core API
against bundled sample files.
"""

from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path

import pytest
from master_of_hwp_studio.server import run as run_studio_server

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples" / "public-official"
HWPX_SAMPLE = SAMPLES_DIR / "table-vpos-01.hwpx"


def _post_json(host: str, port: int, path: str, body: dict[str, object]) -> dict[str, object]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    payload = json.dumps(body).encode("utf-8")
    conn.request(
        "POST",
        path,
        body=payload,
        headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    return dict(json.loads(data))


def _get_json(host: str, port: int, path: str) -> dict[str, object]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", path)
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    return dict(json.loads(data))


@pytest.fixture
def studio_server() -> tuple[str, int]:
    """Start a Studio HTTP server on an ephemeral port for one test."""
    server = run_studio_server("127.0.0.1", 0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield str(host), int(port)
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.skipif(not HWPX_SAMPLE.exists(), reason="HWPX sample missing")
def test_api_status_returns_ok(studio_server: tuple[str, int]) -> None:
    host, port = studio_server
    payload = _get_json(host, port, "/api/status")
    assert payload["ok"] is True
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["integration"]["data"]["ready"] is True


@pytest.mark.skipif(not HWPX_SAMPLE.exists(), reason="HWPX sample missing")
def test_api_browse_lists_sample_directory(studio_server: tuple[str, int]) -> None:
    host, port = studio_server
    payload = _post_json(host, port, "/api/browse", {"path": str(SAMPLES_DIR)})
    assert payload["ok"] is True
    entries = payload["data"]["entries"]
    names = [entry["name"] for entry in entries]
    assert HWPX_SAMPLE.name in names


@pytest.mark.skipif(not HWPX_SAMPLE.exists(), reason="HWPX sample missing")
def test_api_open_then_structure(studio_server: tuple[str, int]) -> None:
    host, port = studio_server
    open_resp = _post_json(host, port, "/api/open", {"path": str(HWPX_SAMPLE)})
    assert open_resp["ok"] is True
    document_id = open_resp["data"]["document_id"]
    assert isinstance(document_id, str)
    structure = _post_json(host, port, "/api/structure", {"document_id": document_id})
    assert structure["ok"] is True
    data = structure["data"]
    assert data["sections_count"] == 1
    assert data["paragraph_count"] > 0
    assert data["table_count"] >= 1


@pytest.mark.skipif(not HWPX_SAMPLE.exists(), reason="HWPX sample missing")
def test_api_open_rejects_missing_path(studio_server: tuple[str, int]) -> None:
    host, port = studio_server
    resp = _post_json(host, port, "/api/open", {"path": ""})
    assert resp["ok"] is False


@pytest.mark.skipif(not HWPX_SAMPLE.exists(), reason="HWPX sample missing")
def test_api_structure_rejects_unknown_document_id(studio_server: tuple[str, int]) -> None:
    host, port = studio_server
    resp = _post_json(host, port, "/api/structure", {"document_id": "bogus"})
    assert resp["ok"] is False


@pytest.mark.skipif(not HWPX_SAMPLE.exists(), reason="HWPX sample missing")
def test_api_save_writes_file(studio_server: tuple[str, int], tmp_path: Path) -> None:
    host, port = studio_server
    open_resp = _post_json(host, port, "/api/open", {"path": str(HWPX_SAMPLE)})
    document_id = open_resp["data"]["document_id"]
    output = tmp_path / "saved.hwpx"
    resp = _post_json(
        host,
        port,
        "/api/save",
        {"document_id": document_id, "path": str(output)},
    )
    assert resp["ok"] is True
    assert output.exists()
    assert output.stat().st_size > 0
