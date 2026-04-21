"""FastMCP server surface for master-of-hwp-studio."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

from master_of_hwp import HwpDocument

try:
    from fastmcp import FastMCP  # type: ignore[import-not-found]
except ImportError:
    FastMCP = None

F = TypeVar("F", bound=Callable[..., object])


class _FallbackMCP:
    """Tiny fallback so tests can import tools without fastmcp installed."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, Callable[..., object]] = {}

    def tool(self) -> Callable[[F], F]:
        """Register a fallback tool."""

        def decorator(func: F) -> F:
            self.tools[func.__name__] = func
            return func

        return decorator

    def run(self) -> None:
        """Fail clearly if someone tries to serve without fastmcp."""
        raise RuntimeError("fastmcp is required to run the MCP server.")


mcp: Any = (
    FastMCP("master-of-hwp-studio") if FastMCP is not None else _FallbackMCP("master-of-hwp-studio")
)


def _tool(func: F) -> F:
    return cast(F, mcp.tool()(func))


@_tool
def open_document(path: str) -> dict[str, object]:
    """Open a HWP/HWPX file and return a compact summary."""
    return HwpDocument.open(path).summary()


@_tool
def find_paragraphs(path: str, query: str, regex: bool = False) -> list[dict[str, object]]:
    """Find paragraphs matching a query in a document."""
    doc = HwpDocument.open(path)
    return [
        {"section": section, "paragraph": paragraph, "text": text}
        for section, paragraph, text in doc.find_paragraphs(query, regex=regex)
    ]


@_tool
def replace_paragraph(
    path: str,
    section_index: int,
    paragraph_index: int,
    new_text: str,
    output_path: str,
) -> dict[str, object]:
    """Replace one paragraph and save the edited document."""
    doc = HwpDocument.open(path)
    edited = doc.replace_paragraph(section_index, paragraph_index, new_text)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(edited.raw_bytes)
    return {"success": True, "output": str(output)}


@_tool
def section_tables(path: str) -> list[list[list[list[list[str]]]]]:
    """Return table structure for each section."""
    return HwpDocument.open(path).section_tables


def run_stdio() -> None:
    """Run the MCP server over stdio."""
    mcp.run()
