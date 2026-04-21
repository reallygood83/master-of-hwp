"""HTTP API backend for master-of-hwp Studio.

Serves the bundled static assets (`master_of_hwp_studio/web/`) and a
JSON API that the web client (`app.js`) consumes.

The server is intentionally thin — it delegates all HWP logic to the
`master_of_hwp` Core API and keeps per-document state in an in-memory
registry. No database, no config files.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from master_of_hwp import HwpDocument

STATIC_FILES = {"/", "/index.html", "/app.css", "/app.js"}
ALLOWED_EXTENSIONS = {".hwp", ".hwpx", ".txt", ".md"}


@dataclass
class _Session:
    """In-memory document session tracked by the server."""

    path: Path
    doc: HwpDocument


class _DocumentRegistry:
    """Thread-unsafe registry of open documents. OK because stdlib
    ThreadingHTTPServer serializes per-connection handler calls and
    the server is single-user / localhost only.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def open(self, path: Path) -> tuple[str, _Session]:
        doc = HwpDocument.open(path)
        document_id = uuid.uuid4().hex
        session = _Session(path=path, doc=doc)
        self._sessions[document_id] = session
        return document_id, session

    def get(self, document_id: str) -> _Session | None:
        return self._sessions.get(document_id)

    def replace(self, document_id: str, new_doc: HwpDocument) -> None:
        if document_id in self._sessions:
            self._sessions[document_id].doc = new_doc


_registry = _DocumentRegistry()


class StudioHandler(BaseHTTPRequestHandler):
    """Custom HTTP handler serving static assets + JSON API."""

    # ---------- HTTP methods ------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(_handle_status())
            return
        if parsed.path in STATIC_FILES:
            self._serve_static(parsed.path)
            return
        self._send_json(
            {"ok": False, "message": f"Not found: {parsed.path}"},
            status=HTTPStatus.NOT_FOUND,
        )

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = self._read_json_body()
        if body is None:
            self._send_json(
                {"ok": False, "message": "Invalid JSON body"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        handler = _POST_ROUTES.get(parsed.path)
        if handler is None:
            self._send_json(
                {"ok": False, "message": f"Unknown endpoint: {parsed.path}"},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        try:
            payload = handler(body)
        except Exception as exc:  # noqa: BLE001 — convert all errors to JSON
            self._send_json({"ok": False, "message": f"{type(exc).__name__}: {exc}"})
            return
        self._send_json(payload)

    # ---------- helpers -----------------------------------------------------

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Quieter logging — only log errors."""
        if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            super().log_message(format, *args)

    def _serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        filename = path.lstrip("/")
        try:
            web_root = resources.files("master_of_hwp_studio.web")
            file_ref = web_root.joinpath(filename)
            data = file_ref.read_bytes()
        except (FileNotFoundError, OSError):
            self._send_json(
                {"ok": False, "message": f"Static not found: {filename}"},
                status=HTTPStatus.NOT_FOUND,
            )
            return
        content_type = _content_type_for(filename)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _send_json(
        self,
        payload: dict[str, Any],
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------- endpoint implementations ----------------------------------------


def _handle_status() -> dict[str, Any]:
    import shutil

    providers: list[str] = []
    provider_sources: dict[str, str] = {}
    if shutil.which("claude"):
        providers.append("claude")
        provider_sources["claude"] = "cli"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("claude")
        provider_sources["claude"] = "api"
    if shutil.which("codex"):
        providers.append("codex")
        provider_sources["codex"] = "cli"
    elif os.environ.get("OPENAI_API_KEY"):
        providers.append("codex")
        provider_sources["codex"] = "api"
    return {
        "ok": True,
        "data": {
            "version": "0.4.0",
            "integration": {"data": {"ready": True}},
            "providers": providers or ["claude", "codex"],
            "provider_sources": provider_sources,
            "editor_url": "http://127.0.0.1:7700/",
        },
    }


def _handle_browse(body: dict[str, Any]) -> dict[str, Any]:
    raw_path = str(body.get("path", "")) or os.path.expanduser("~")
    current = Path(raw_path).expanduser().resolve()
    if not current.exists() or not current.is_dir():
        return {"ok": False, "message": f"Not a directory: {current}"}
    parent = current.parent if current != current.parent else None
    entries: list[dict[str, str]] = []
    try:
        items = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return {"ok": False, "message": f"Permission denied: {current}"}
    for item in items:
        if item.name.startswith("."):
            continue
        is_dir = item.is_dir()
        if not is_dir and item.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        entries.append(
            {
                "type": "dir" if is_dir else "file",
                "name": item.name,
                "path": str(item),
            }
        )
    return {
        "ok": True,
        "data": {
            "current_path": str(current),
            "parent_path": str(parent) if parent else "",
            "entries": entries,
        },
    }


def _handle_open(body: dict[str, Any]) -> dict[str, Any]:
    raw = str(body.get("path", "")).strip()
    if not raw:
        return {"ok": False, "message": "path is required"}
    path = Path(raw).expanduser().resolve()
    try:
        document_id, session = _registry.open(path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"Open failed: {exc}"}
    return {
        "ok": True,
        "data": {
            "document_id": document_id,
            "path": str(session.path),
            "format": session.doc.source_format.value,
        },
    }


def _handle_structure(body: dict[str, Any]) -> dict[str, Any]:
    document_id = str(body.get("document_id", ""))
    session = _registry.get(document_id)
    if session is None:
        return {"ok": False, "message": "Unknown document_id"}
    doc = session.doc
    paragraphs = doc.section_paragraphs
    paragraph_count = sum(len(s) for s in paragraphs)
    table_count = sum(len(s) for s in doc.section_tables)
    sections_data = [
        {
            "index": section_index,
            "paragraphs": [
                {"index": para_index, "text": text}
                for para_index, text in enumerate(section_paragraphs)
            ],
        }
        for section_index, section_paragraphs in enumerate(paragraphs)
    ]
    return {
        "ok": True,
        "data": {
            "paragraph_count": paragraph_count,
            "table_count": table_count,
            "sections_count": doc.sections_count,
            "sections": sections_data,
            "summary": doc.summary(max_preview=100, preview_count=5),
        },
    }


def _handle_save(body: dict[str, Any]) -> dict[str, Any]:
    document_id = str(body.get("document_id", ""))
    output_path = str(body.get("path", "")).strip()
    session = _registry.get(document_id)
    if session is None:
        return {"ok": False, "message": "Unknown document_id"}
    if not output_path:
        return {"ok": False, "message": "path is required"}
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(session.doc.raw_bytes)
    return {"ok": True, "data": {"saved_path": str(target)}}


def _handle_file_bytes(body: dict[str, Any]) -> dict[str, Any]:
    raw = str(body.get("path", "")).strip()
    if not raw:
        return {"ok": False, "message": "path is required"}
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        return {"ok": False, "message": f"Not found: {path}"}
    data = path.read_bytes()
    return {
        "ok": True,
        "data": {
            "path": str(path),
            "file_name": path.name,
            "base64": base64.b64encode(data).decode("ascii"),
            "size": len(data),
        },
    }


def _handle_ai_preview(body: dict[str, Any]) -> dict[str, Any]:
    """Generate a new-content preview for a paragraph-scoped edit."""
    document_id = str(body.get("document_id", ""))
    instruction = _instruction_from(body)
    paragraph_index = _as_int(body.get("paragraph_index"))
    task_type = str(body.get("task_type", "rewrite"))
    provider_key = str(body.get("provider", "claude"))
    session = _registry.get(document_id)
    if session is None:
        return {"ok": False, "message": "Unknown document_id"}
    if paragraph_index is None:
        return {"ok": False, "message": "paragraph_index is required"}
    paragraphs = session.doc.section_paragraphs
    target_text = _paragraph_text_at(paragraphs, 0, paragraph_index)
    if target_text is None:
        return {"ok": False, "message": f"paragraph_index {paragraph_index} out of range"}

    new_content = _generate_edit_content(
        provider_key=provider_key,
        task_type=task_type,
        original=target_text,
        instruction=instruction,
    )
    return {
        "ok": True,
        "data": {
            "task_type": task_type,
            "paragraph_index": paragraph_index,
            "content": new_content,
            "original": target_text,
            "provider": provider_key,
        },
    }


def _handle_ai_preview_selection(body: dict[str, Any]) -> dict[str, Any]:
    """Generate a new-content preview for a drag-selection edit."""
    document_id = str(body.get("document_id", ""))
    instruction = _instruction_from(body)
    selection = body.get("selection") or {}
    task_type = str(body.get("task_type", "rewrite"))
    provider_key = str(body.get("provider", "claude"))
    session = _registry.get(document_id)
    if session is None:
        return {"ok": False, "message": "Unknown document_id"}
    selected_text = str((selection or {}).get("text", "")).strip()
    if not selected_text:
        return {"ok": False, "message": "selection.text is required"}

    new_content = _generate_edit_content(
        provider_key=provider_key,
        task_type=task_type,
        original=selected_text,
        instruction=instruction,
    )
    return {
        "ok": True,
        "data": {
            "task_type": task_type,
            "selection": selection,
            "content": new_content,
            "original": selected_text,
            "provider": provider_key,
        },
    }


def _handle_ai_apply(body: dict[str, Any]) -> dict[str, Any]:
    """Apply a previewed paragraph edit to the document."""
    document_id = str(body.get("document_id", ""))
    paragraph_index = _as_int(body.get("paragraph_index"))
    content = str(body.get("content", "")).strip()
    session = _registry.get(document_id)
    if session is None:
        return {"ok": False, "message": "Unknown document_id"}
    if paragraph_index is None or not content:
        return {"ok": False, "message": "paragraph_index and content are required"}
    try:
        new_doc = session.doc.replace_paragraph(0, paragraph_index, content)
    except (IndexError, Exception) as exc:  # noqa: BLE001
        return {"ok": False, "message": f"Apply failed: {exc}"}
    _registry.replace(document_id, new_doc)
    return {"ok": True, "data": {"status": "applied", "paragraph_index": paragraph_index}}


def _handle_ai_apply_selection(body: dict[str, Any]) -> dict[str, Any]:
    """Apply an edit to the paragraph that contains the user's selection."""
    document_id = str(body.get("document_id", ""))
    selection = body.get("selection") or {}
    content = str(body.get("content", "")).strip()
    session = _registry.get(document_id)
    if session is None:
        return {"ok": False, "message": "Unknown document_id"}
    if not content:
        return {"ok": False, "message": "content is required"}
    start = (selection or {}).get("start") or {}
    para_index = _as_int(start.get("paragraphIndex"))
    if para_index is None:
        return {"ok": False, "message": "selection.start.paragraphIndex is required"}
    try:
        new_doc = session.doc.replace_paragraph(0, para_index, content)
    except (IndexError, Exception) as exc:  # noqa: BLE001
        return {"ok": False, "message": f"Apply failed: {exc}"}
    _registry.replace(document_id, new_doc)
    return {"ok": True, "data": {"status": "applied", "paragraph_index": para_index}}


def _instruction_from(body: dict[str, Any]) -> str:
    return str(body.get("instruction") or body.get("request") or "").strip()


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _paragraph_text_at(paragraphs: list[list[str]], section: int, index: int) -> str | None:
    if section < 0 or section >= len(paragraphs):
        return None
    items = paragraphs[section]
    if index < 0 or index >= len(items):
        return None
    return items[index]


def _generate_edit_content(
    *,
    provider_key: str,
    task_type: str,
    original: str,
    instruction: str,
) -> str:
    """Return new paragraph text using the selected provider, or a
    deterministic rule-based fallback if no API key / provider is available.
    """
    provider = _build_provider(provider_key)
    system_prompt = (
        "You are a helpful HWP document editor assistant. "
        "Return ONLY the rewritten text, no explanations, no quotes. "
        "Preserve the original language (Korean input → Korean output)."
    )
    user_prompt = _build_edit_user_prompt(task_type, original, instruction)
    if provider is not None:
        try:
            result = provider.complete(system_prompt, user_prompt, max_tokens=800)
            if result:
                return result.strip().strip('"').strip("'")
        except Exception:  # noqa: BLE001 — fall back to rule-based below
            pass
    return _rule_based_edit(task_type, original, instruction)


def _build_edit_user_prompt(task_type: str, original: str, instruction: str) -> str:
    header = {
        "rewrite": "사용자 지시에 따라 아래 문단을 다시 쓰세요.",
        "summarize": "아래 문단을 한 줄로 요약하세요.",
        "insert": "아래 문단 다음에 이어질 자연스러운 새 문단을 작성하세요.",
    }.get(task_type, "사용자 지시에 따라 아래 문단을 편집하세요.")
    return (
        f"{header}\n\n"
        f"지시: {instruction or '(별도 지시 없음)'}\n\n"
        f"원문:\n{original}\n\n"
        f"결과:"
    )


def _rule_based_edit(task_type: str, original: str, instruction: str) -> str:
    """Deterministic no-LLM fallback so the UI still shows something useful."""
    if task_type == "summarize":
        first_line = original.splitlines()[0] if original else ""
        truncated = first_line[:60]
        return f"{truncated}…" if len(first_line) > 60 else truncated
    if task_type == "insert":
        return f"[추가 문단 — LLM 응답 불가: {instruction or '지시 없음'}]"
    suffix = f" [{instruction}]" if instruction else " [편집]"
    return original + suffix


def _build_provider(provider_key: str) -> Any:
    """Instantiate an LLMProvider for the given key, or return None.

    Preference order per provider name:
    - "claude" / "claude-code": Claude Code CLI (subscription) → Anthropic API
    - "codex" / "openai":       Codex CLI (subscription) → OpenAI API

    CLI path is preferred because it leverages the user's existing
    subscription (no API key configuration required).
    """
    key = provider_key.lower().strip()
    if key in {"claude", "claude-code", "anthropic"}:
        return _build_claude_cli() or _build_anthropic()
    if key in {"codex", "openai", "gpt", "codex-cli"}:
        return _build_codex_cli() or _build_openai()
    # Unknown name — try everything in sensible order.
    return _build_claude_cli() or _build_codex_cli() or _build_anthropic() or _build_openai()


def _build_claude_cli() -> Any:
    try:
        from master_of_hwp.ai.providers import ClaudeCodeCLIProvider

        return ClaudeCodeCLIProvider()
    except Exception:  # noqa: BLE001 — includes "not on PATH"
        return None


def _build_codex_cli() -> Any:
    try:
        from master_of_hwp.ai.providers import CodexCLIProvider

        return CodexCLIProvider()
    except Exception:  # noqa: BLE001
        return None


def _build_anthropic() -> Any:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from master_of_hwp.ai.providers import AnthropicProvider

        return AnthropicProvider()
    except Exception:  # noqa: BLE001
        return None


def _build_openai() -> Any:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from master_of_hwp.ai.providers import OpenAIProvider

        return OpenAIProvider()
    except Exception:  # noqa: BLE001
        return None


def _content_type_for(filename: str) -> str:
    if filename.endswith(".html"):
        return "text/html; charset=utf-8"
    if filename.endswith(".css"):
        return "text/css; charset=utf-8"
    if filename.endswith(".js"):
        return "application/javascript; charset=utf-8"
    return "application/octet-stream"


_POST_ROUTES: dict[str, Any] = {
    "/api/browse": _handle_browse,
    "/api/open": _handle_open,
    "/api/structure": _handle_structure,
    "/api/save": _handle_save,
    "/api/file-bytes": _handle_file_bytes,
    "/api/ai/preview": _handle_ai_preview,
    "/api/ai/preview-selection": _handle_ai_preview_selection,
    "/api/ai/apply": _handle_ai_apply,
    "/api/ai/apply-selection": _handle_ai_apply_selection,
}


def run(host: str, port: int) -> ThreadingHTTPServer:
    """Create and return the HTTP server; caller is responsible for
    `serve_forever()`.
    """
    return ThreadingHTTPServer((host, port), StudioHandler)
