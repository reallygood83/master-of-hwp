"""Command-line interface for master-of-hwp-studio."""

from __future__ import annotations

import json
import socket
import threading
import webbrowser

import click

from master_of_hwp_studio.server import run as run_studio_server


@click.group()
def main() -> None:
    """master-of-hwp-studio — AI-powered HWP editing."""


@main.command()
@click.option("--port", default=8000, show_default=True, help="Studio web port.")
@click.option("--editor-port", default=7700, show_default=True, help="Reserved editor port.")
@click.option("--open-browser/--no-open-browser", default=True, show_default=True)
def studio(port: int, editor_port: int, open_browser: bool) -> None:
    """Start the Studio HTTP server (static assets + JSON API)."""
    actual_port = _find_free_port(port)
    server = run_studio_server("127.0.0.1", actual_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{actual_port}"
    click.echo(f"master-of-hwp Studio: {url}")
    click.echo(f"Editor port reserved: {editor_port} (rhwp editor — optional)")
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


@main.command("mcp-serve")
def mcp_serve() -> None:
    """Run the MCP server over stdio (for Claude Desktop)."""
    from master_of_hwp_studio.mcp.server import run_stdio

    run_stdio()


@main.command("mcp-config")
def mcp_config() -> None:
    """Print Claude Desktop MCP config snippet for copy-paste."""
    click.echo(_mcp_config_text())


def _mcp_config_text() -> str:
    config_path = "~/Library/Application Support/Claude/claude_desktop_config.json"
    snippet = {
        "mcpServers": {
            "master-of-hwp": {
                "command": "mohwp",
                "args": ["mcp-serve"],
            }
        }
    }
    return f"# Add to {config_path}:\n{json.dumps(snippet, indent=2, ensure_ascii=False)}"


def _find_free_port(preferred: int) -> int:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
