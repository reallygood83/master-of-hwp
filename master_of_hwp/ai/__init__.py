"""Agentic layer: intent parsing, planning, execution, verification.

The ai package is the bridge between natural language and the
structural operations in master_of_hwp.operations. It is pluggable:
LLM providers are injected via ai.providers.LLMProvider Protocol.

Layered pipeline:
    intent.parse_edit_intent() -> planner.plan_operations() ->
    operations.execute() -> fidelity.verify()
"""

from master_of_hwp.ai.intent import EditIntent, parse_edit_intent

__all__ = ["EditIntent", "parse_edit_intent"]
