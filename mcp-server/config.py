from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


@dataclass(frozen=True)
class Settings:
    project_root: Path
    allowed_workspace: Path
    rhwp_extract_command: str | None
    default_max_chars: int = 50_000


def _default_rhwp_extract_command(project_root: Path) -> str | None:
    bridge_path = project_root / "mcp-server" / "bridges" / "rhwp_extract.mjs"
    node_path = shutil.which("node")
    if not node_path or not bridge_path.exists():
        return None
    return (
        f'"{node_path}" "{bridge_path}" "{{input}}" '
        f'--include-tables={{include_tables}} --max-chars={{max_chars}}'
    )


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parent.parent
    default_workspace = Path.home()
    allowed_workspace = Path(
        os.getenv("MASTER_OF_HWP_ALLOWED_WORKSPACE", str(default_workspace))
    ).expanduser().resolve()
    rhwp_extract_command = os.getenv("RHWP_EXTRACT_COMMAND") or _default_rhwp_extract_command(
        project_root
    )
    return Settings(
        project_root=project_root,
        allowed_workspace=allowed_workspace,
        rhwp_extract_command=rhwp_extract_command,
    )


SETTINGS = load_settings()
