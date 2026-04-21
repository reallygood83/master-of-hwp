"""Agentic layer: intent parsing, locating, operations, rollback.

The `ai` package is the bridge between natural language and the
structural operations that edit `HwpDocument`. It is pluggable:
eventual LLM providers are injected via a Protocol.

Pipeline:
    intent.parse_edit_intent()
        -> locator.locate_targets()
        -> operations.apply()
        -> fidelity.verify()
        -> rollback.RollbackTransaction on failure

v0.1 scaffolds: only `intent.parse_edit_intent()` and
`ReplaceOperation.apply()` are live. Other entry points raise
`NotImplementedError` with a target version.
"""

from master_of_hwp.ai.intent import EditIntent, parse_edit_intent, parse_intent_llm
from master_of_hwp.ai.locator import LocatorScope, ParagraphLocator, locate_targets
from master_of_hwp.ai.operations import (
    DeleteOperation,
    EditOperation,
    InsertOperation,
    ReplaceOperation,
)
from master_of_hwp.ai.rollback import RollbackTransaction

__all__ = [
    "DeleteOperation",
    "EditIntent",
    "EditOperation",
    "InsertOperation",
    "LocatorScope",
    "ParagraphLocator",
    "ReplaceOperation",
    "RollbackTransaction",
    "locate_targets",
    "parse_edit_intent",
    "parse_intent_llm",
]
