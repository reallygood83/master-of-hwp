"""Command-line interface for master-of-hwp-studio."""

from __future__ import annotations

import json
import socket
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

import click

from master_of_hwp_studio.server import run as run_studio_server


@click.group()
def main() -> None:
    """master-of-hwp-studio — AI-powered HWP editing."""


@main.command()
@click.option("--port", default=8000, show_default=True, help="Studio web port.")
@click.option("--editor-port", default=7700, show_default=True, help="rhwp editor port.")
@click.option("--open-browser/--no-open-browser", default=True, show_default=True)
@click.option(
    "--with-editor/--no-editor",
    default=True,
    show_default=True,
    help="Start the bundled rhwp WYSIWYG editor on --editor-port.",
)
def studio(port: int, editor_port: int, open_browser: bool, with_editor: bool) -> None:
    """Start the Studio HTTP server + bundled rhwp editor (WYSIWYG)."""
    actual_port = _find_free_port(port)
    server = run_studio_server("127.0.0.1", actual_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{actual_port}"

    editor_server = None
    editor_status = "disabled"
    if with_editor:
        editor_dir = _rhwp_editor_dir()
        if editor_dir is None or not editor_dir.exists():
            editor_status = "not bundled"
        else:
            try:
                handler = partial(SimpleHTTPRequestHandler, directory=str(editor_dir))
                editor_server = ThreadingHTTPServer(("127.0.0.1", editor_port), handler)
                editor_thread = threading.Thread(target=editor_server.serve_forever, daemon=True)
                editor_thread.start()
                editor_status = "bundled"
            except OSError:
                editor_status = "external"  # Something already on port 7700; assume it's rhwp.

    click.echo(f"master-of-hwp Studio: {url}")
    if editor_status == "bundled":
        click.echo(f"rhwp editor:          http://127.0.0.1:{editor_port} (bundled)")
    elif editor_status == "external":
        click.echo(
            f"rhwp editor:          http://127.0.0.1:{editor_port} (external process detected)"
        )
    elif editor_status == "not bundled":
        click.echo("rhwp editor:          NOT bundled — WYSIWYG editor unavailable")
        click.echo("                      → pip install --upgrade master-of-hwp-studio")
    else:
        click.echo("rhwp editor:          disabled (--no-editor)")
    click.echo("")
    click.echo(_mcp_config_text())
    click.echo("")
    click.echo("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()
        if editor_server is not None:
            editor_server.shutdown()


@main.command("mcp-serve")
def mcp_serve() -> None:
    """Run the MCP server over stdio (for Claude Desktop)."""
    from master_of_hwp_studio.mcp.server import run_stdio

    run_stdio()


@main.command("mcp-config")
def mcp_config() -> None:
    """Print Claude Desktop MCP config snippet for copy-paste."""
    click.echo(_mcp_config_text())


def _claude_desktop_config_path() -> str:
    """Return OS-specific Claude Desktop config path for display.

    Reference: https://modelcontextprotocol.io/quickstart/user
    """
    if sys.platform == "darwin":
        return "~/Library/Application Support/Claude/claude_desktop_config.json"
    if sys.platform == "win32":
        return "%APPDATA%\\Claude\\claude_desktop_config.json"
    # Linux / others
    return "~/.config/Claude/claude_desktop_config.json"


def _mcp_config_text() -> str:
    config_path = _claude_desktop_config_path()
    snippet = {
        "mcpServers": {
            "master-of-hwp": {
                "command": "mohwp",
                "args": ["mcp-serve"],
            }
        }
    }
    return f"# Add to {config_path}:\n{json.dumps(snippet, indent=2, ensure_ascii=False)}"


def _rhwp_editor_dir() -> Path | None:
    """Return the path to the bundled rhwp editor dist, or None if missing."""
    try:
        resource = resources.files("master_of_hwp_studio").joinpath("rhwp_editor")
    except (ModuleNotFoundError, FileNotFoundError):
        return None
    try:
        # Materialize the traversable into a real filesystem path for SimpleHTTPRequestHandler.
        with resources.as_file(resource) as path:
            return Path(path)
    except (FileNotFoundError, NotADirectoryError):
        return None


def _find_free_port(preferred: int) -> int:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
