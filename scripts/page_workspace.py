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

# 入口候选：单入口形态用 main.tex；形态 B（独立做题本入口）还会有 main-workbook.tex。
# 审计以**完整书入口**为准，因为它声明了全部内容模块；做题本入口只是同一份内容的视图。
ENTRY_CANDIDATES = ("main.tex", "main-workbook.tex")


def resolve_entry(project: Path) -> Path:
    """返回用于审计的入口文件。

    优先完整书入口；项目只提供做题本入口时退回到它。都找不到时报错，让调用方
    给出可读提示，而不是静默用一个不存在的路径。
    """

    latex_root = project / "latex"
    for name in ENTRY_CANDIDATES:
        candidate = latex_root / name
        if candidate.is_file():
            return candidate
    listed = "、".join(f"latex/{name}" for name in ENTRY_CANDIDATES)
    raise FileNotFoundError(f"找不到入口文件（{listed}）")
