from __future__ import annotations

import base64
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from config import SETTINGS
from gui_ai import ai_apply_selection_tool, ai_apply_tool, ai_preview_tool, ai_selection_preview_tool
from tools.extract_document_structure import extract_document_structure_tool
from tools.extract_document_text import extract_document_text_tool
from tools.insert_paragraph_after import insert_paragraph_after_tool
from tools.open_document import open_document_tool
from tools.replace_paragraph_text import replace_paragraph_text_tool
from tools.rhwp_integration_status import rhwp_integration_status_tool
from tools.rhwp_save_status import rhwp_save_status_tool
from tools.save_as import save_as_tool
from tools.validate_document import validate_document_tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUI_DIR = PROJECT_ROOT / "gui"
HOST = os.getenv("MASTER_OF_HWP_GUI_HOST", "127.0.0.1")
PORT = int(os.getenv("MASTER_OF_HWP_GUI_PORT", "8876"))
ALLOWED_EXTENSIONS = {".hwp", ".hwpx", ".txt", ".md"}


class GUIHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(
                {
                    "ok": True,
                    "integration": rhwp_integration_status_tool(),
                    "save": rhwp_save_status_tool(),
                    "allowed_workspace": str(SETTINGS.allowed_workspace),
                    "editor_url": "http://127.0.0.1:7700/",
                    "providers": ["claude", "codex", "opencode"],
                }
            )
            return

        if parsed.path == "/" or parsed.path in {"/index.html", "/app.js", "/app.css"}:
            self._serve_static(parsed.path)
            return

        self._send_json({"ok": False, "message": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self._read_json_body()
        if body is None:
            self._send_json({"ok": False, "message": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return

        routes = {
            "/api/browse": self._browse,
            "/api/file-bytes": self._file_bytes,
            "/api/open": lambda data: open_document_tool(
                path=str(data.get("path", "")),
                readonly=bool(data.get("readonly", False)),
            ),
            "/api/text": lambda data: extract_document_text_tool(
                path=str(data.get("path", "")),
                document_id=str(data.get("document_id", "")),
            ),
            "/api/structure": lambda data: extract_document_structure_tool(
                path=str(data.get("path", "")),
                document_id=str(data.get("document_id", "")),
            ),
            "/api/replace": lambda data: replace_paragraph_text_tool(
                document_id=str(data.get("document_id", "")),
                paragraph_index=int(data.get("paragraph_index", 0)),
                new_text=str(data.get("new_text", "")),
            ),
            "/api/insert": lambda data: insert_paragraph_after_tool(
                document_id=str(data.get("document_id", "")),
                after_paragraph_index=int(data.get("after_paragraph_index", 0)),
                text=str(data.get("text", "")),
            ),
            "/api/ai/preview": lambda data: ai_preview_tool(
                provider=str(data.get("provider", "claude")),
                document_id=str(data.get("document_id", "")),
                paragraph_index=int(data.get("paragraph_index", 0)),
                task_type=str(data.get("task_type", "rewrite")),
                instruction=str(data.get("instruction", "")),
            ),
            "/api/ai/preview-selection": lambda data: ai_selection_preview_tool(
                provider=str(data.get("provider", "claude")),
                selection=data.get("selection") if isinstance(data.get("selection"), dict) else {},
                task_type=str(data.get("task_type", "rewrite")),
                instruction=str(data.get("instruction", "")),
                document_id=str(data.get("document_id", "")),
            ),
            "/api/ai/apply": lambda data: ai_apply_tool(
                document_id=str(data.get("document_id", "")),
                task_type=str(data.get("task_type", "rewrite")),
                paragraph_index=int(data.get("paragraph_index", 0)),
                content=str(data.get("content", "")),
            ),
            "/api/ai/apply-selection": lambda data: ai_apply_selection_tool(
                document_id=str(data.get("document_id", "")),
                selection=data.get("selection") if isinstance(data.get("selection"), dict) else {},
                content=str(data.get("content", "")),
            ),
            "/api/save": lambda data: save_as_tool(
                document_id=str(data.get("document_id", "")),
                output_path=str(data.get("output_path", "")),
            ),
            "/api/validate": lambda data: validate_document_tool(
                path=str(data.get("path", "")),
            ),
        }

        handler = routes.get(parsed.path)
        if handler is None:
            self._send_json({"ok": False, "message": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            result = handler(body)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "message": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(result)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _browse(self, data: dict[str, object]) -> dict[str, object]:
        requested = str(data.get("path") or SETTINGS.allowed_workspace)
        candidate = Path(requested).expanduser().resolve()
        try:
            _ = candidate.relative_to(SETTINGS.allowed_workspace)
        except ValueError:
            candidate = SETTINGS.allowed_workspace
        if candidate.is_file():
            candidate = candidate.parent
        if not candidate.exists() or not candidate.is_dir():
            candidate = SETTINGS.allowed_workspace

        parent = candidate.parent if candidate != SETTINGS.allowed_workspace else candidate
        entries: list[dict[str, object]] = []
        for child in sorted(candidate.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.is_dir():
                entries.append({"name": child.name, "path": str(child), "type": "dir"})
                continue
            if child.suffix.lower() in ALLOWED_EXTENSIONS:
                entries.append({"name": child.name, "path": str(child), "type": "file"})

        return {
            "ok": True,
            "message": "directory listed",
            "data": {
                "current_path": str(candidate),
                "parent_path": str(parent),
                "entries": entries,
            },
        }

    def _file_bytes(self, data: dict[str, object]) -> dict[str, object]:
        requested = str(data.get("path") or "")
        candidate = Path(requested).expanduser().resolve()
        try:
            _ = candidate.relative_to(SETTINGS.allowed_workspace)
        except ValueError:
            return {"ok": False, "message": "Path is outside the allowed workspace."}
        if not candidate.exists() or not candidate.is_file():
            return {"ok": False, "message": "File not found."}
        raw = candidate.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        return {
            "ok": True,
            "message": "file bytes loaded",
            "data": {
                "path": str(candidate),
                "file_name": candidate.name,
                "base64": encoded,
                "size": len(raw),
            },
        }

    def _read_json_body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _serve_static(self, path: str) -> None:
        file_name = "index.html" if path in {"/", "/index.html"} else path.lstrip("/")
        target = GUI_DIR / file_name
        if not target.exists():
            self._send_json({"ok": False, "message": "Static asset not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8"
        if target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        payload = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), GUIHandler)
    print(f"master-of-hwp GUI running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
