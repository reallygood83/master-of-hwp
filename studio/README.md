# master-of-hwp-studio

One-click local Studio for `master-of-hwp`: a small CLI, a bundled web UI, and MCP tools that sit on top of the Core API.

```bash
pip install master-of-hwp-studio
mohwp studio
```

The `studio` command starts a local static web UI and prints a Claude Desktop MCP configuration snippet.

## Commands

```bash
mohwp studio --port 8000 --editor-port 7700
mohwp mcp-config
mohwp mcp-serve
```

`mcp-serve` runs the FastMCP server over stdio for Claude Desktop.
