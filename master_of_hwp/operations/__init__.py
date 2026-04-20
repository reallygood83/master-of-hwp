"""Edit operations (atomic, pure, immutable).

Each operation takes a HwpDocument plus parameters and returns a new
HwpDocument. Operations never mutate inputs. They may raise
OperationError on invalid inputs.

Phase 1 scope: text replace/insert/delete, paragraph insertion, basic table
creation. Advanced structural operations land in Phase 2+.
"""


class OperationError(Exception):
    """Raised when an edit operation cannot complete safely."""


__all__ = ["OperationError"]
