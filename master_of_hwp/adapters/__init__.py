"""Adapters bridge Core API to external engines and consumers.

    * rhwp_bridge — invokes the Rust-based rhwp engine for parsing/saving
    * mcp_adapter — exposes Core API as an MCP server surface

Keeping these thin isolates Core from engine churn.
"""
