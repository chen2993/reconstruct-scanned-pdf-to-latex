"""拆页临时工作区的路径解析。

唯一规范名是 ``extracted``；所有脚本通过本模块取路径，避免常量重复。
"""

from __future__ import annotations

from pathlib import Path

CONTROL_DIR = ".reconstruct-scanned-pdf-to-latex"
WORKSPACE_NAME = "extracted"


def control_dir(project: Path) -> Path:
    return project / CONTROL_DIR


def resolve_workspace(project: Path, create: bool = False) -> Path:
    """Return the page workspace, creating it when requested."""
    workspace = control_dir(project) / WORKSPACE_NAME
    if create:
        workspace.mkdir(parents=True, exist_ok=True)
    return workspace
