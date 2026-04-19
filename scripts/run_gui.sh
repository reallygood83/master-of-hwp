#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_DIR="$PROJECT_ROOT/mcp-server"
VENV_PYTHON="$MCP_DIR/.venv/bin/python"
export MASTER_OF_HWP_GUI_HOST="${MASTER_OF_HWP_GUI_HOST:-127.0.0.1}"
export MASTER_OF_HWP_GUI_PORT="${MASTER_OF_HWP_GUI_PORT:-8876}"
export MASTER_OF_HWP_ALLOWED_WORKSPACE="${MASTER_OF_HWP_ALLOWED_WORKSPACE:-$HOME}"

cd "$MCP_DIR"
if [ -x "$VENV_PYTHON" ]; then
  exec "$VENV_PYTHON" gui_server.py
fi
exec python3 gui_server.py
