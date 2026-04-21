"""master_of_hwp — Open-source platform for safe, AI-assisted HWP editing.

Public API entry points:

    from master_of_hwp import HwpDocument

See docs/ROADMAP.md and docs/ARCHITECTURE.md for the platform vision.
"""

from master_of_hwp.core.document import AIEditResult, HwpDocument

__all__ = ["AIEditResult", "HwpDocument"]
__version__ = "0.1.0"
