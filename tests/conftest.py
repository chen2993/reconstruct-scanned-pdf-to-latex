"""共享夹具：构造最小但语义完整的重建项目。"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

BS = chr(92)
REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def run_script(name: str, *args: object, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run one skill script and capture text output."""
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / name), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
    )


@pytest.fixture
def run():
    return run_script

# 一个自洽的最小配置：所有者、父级白名单、跨页所有者都只覆盖项目实际用到的域，
# 其余域显式写成空集合，避免与默认集合混用而互相冲突。
MINIMAL_CONFIG = {
    "owner_environments": ["bookbody", "booktext", "bookexample", "bookanswer"],
    "owner_parent_environments": {
        "booktext": ["bookbody"],
        "bookexample": ["bookbody"],
        "bookanswer": ["bookexample"],
    },
    "cross_page_owner_environments": ["bookexample", "bookanswer"],
    "question_owner_environments": ["bookexample"],
    "answer_owner_environments": ["bookanswer"],
    "answer_media_environments": [],
    "media_environments": [
        "figure",
        "table",
        "tabular",
        "tikzpicture",
        "itemize",
        "enumerate",
        "center",
        "equation",
        "align",
    ],
}


def plain_page(number: int) -> str:
    """A single well-formed body page."""
    return (
        f"% Source page: pages-{number:03d}\n"
        + BS + "begin{bookbody}\n"
        + BS + "begin{booktext}\n"
        + f"正文第 {number} 页。\n"
        + BS + "end{booktext}\n"
        + BS + "end{bookbody}\n"
    )


def stub_page(number: int) -> str:
    return (
        "% Generated page stub; replace with reconstructed content.\n"
        f"% Source page: pages-{number:03d}\n"
    )


@dataclass
class Project:
    root: Path

    @property
    def control(self) -> Path:
        return self.root / ".reconstruct-scanned-pdf-to-latex"

    @property
    def pages(self) -> Path:
        return self.root / "latex" / "pages"

    def write_page(self, number: int, content: str) -> None:
        (self.pages / f"pages-{number:03d}.tex").write_text(content, encoding="utf-8")

    def write_config(self, payload: dict) -> None:
        self.control.mkdir(parents=True, exist_ok=True)
        (self.control / "semantic-audit.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def dispatch_state(self) -> dict:
        return json.loads((self.control / "dispatch.json").read_text(encoding="utf-8"))


def build_project(root: Path, body_end: int, config: dict | None = None) -> Project:
    """Create a minimal project whose body range is ``1..body_end``.

    Pages start as stubs, mirroring the real flow: scaffolding produces
    placeholders that content units later replace.
    """
    for part in ("latex/front", "latex/pages", "latex/back"):
        (root / part).mkdir(parents=True, exist_ok=True)
    (root / "latex" / "main.tex").write_text(
        BS + "input{front/cover}\n"
        + BS + f"bookinput{{1}}{{{body_end}}}\n",
        encoding="utf-8",
    )
    # 与 renumber_pages.py 生成的骨架一致：模块必须列出其覆盖的最终标识，
    # 否则 audit_provenance 的模块覆盖检查会报 missing_module_coverage。
    (root / "latex" / "front" / "cover.tex").write_text(
        "% Generated logical module stub; replace with reconstructed content.\n"
        "% Module: cover\n"
        "% Source pages:\n"
        "%   front-001\n"
        + BS + "bookmaketoc\n",
        encoding="utf-8",
    )
    project = Project(root)
    project.write_config(config if config is not None else MINIMAL_CONFIG)
    (project.control / "style-cards.md").write_text(
        "# 样式卡片\n\n- 样式摘要版本：v1\n", encoding="utf-8"
    )
    for number in range(1, body_end + 1):
        project.write_page(number, stub_page(number))
    return project


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return build_project(tmp_path / "proj", body_end=2)


@pytest.fixture
def batch_project(tmp_path: Path) -> Project:
    return build_project(tmp_path / "proj", body_end=25)
