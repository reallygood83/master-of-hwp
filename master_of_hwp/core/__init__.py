"""Core domain model: HwpDocument and its constituent parts.

All types in this package are immutable (frozen dataclasses) to guarantee
safety under concurrent access and to make edits functional (return new values).
"""

from master_of_hwp.core.document import HwpDocument, SourceFormat

__all__ = ["HwpDocument", "SourceFormat"]
