"""Adapters bridge Core API to external engines and consumers.

    * hwp5_reader — HWP 5.0 compound-file introspection (via olefile)
    * hwpx_reader — HWPX (OOXML/ZIP) introspection [Phase 0 spike #002]
    * rhwp_bridge — invokes the Rust-based rhwp engine for parsing/saving
    * mcp_adapter — exposes Core API as an MCP server surface

Keeping these thin isolates Core from engine churn.
"""

from master_of_hwp.adapters.hwp5_reader import Hwp5FormatError, count_sections

__all__ = ["Hwp5FormatError", "count_sections"]
