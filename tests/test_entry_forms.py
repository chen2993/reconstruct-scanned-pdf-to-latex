"""入口形态：单入口与独立做题本入口都必须被审计与调度接受。

做题本的入口组织有两条成熟路线（单入口 + 类文件开关；独立 main-workbook.tex），
但它们共享同一份题目源码。审计与调度只该关心"正文范围是谁声明的"，不该绑定
某个文件名或某条命令。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import BS, SCRIPTS


def make_project(root: Path, entry: str, body_command: str) -> Path:
    for part in ("latex/front", "latex/pages", "latex/back"):
        (root / part).mkdir(parents=True, exist_ok=True)
    control = root / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True, exist_ok=True)

    (root / "latex" / "front" / "cover.tex").write_text(
        "% Generated logical module stub; replace with reconstructed content.\n"
        "% Module: cover\n% Source pages:\n%   front-001\n"
        + BS + "bookmaketoc\n",
        encoding="utf-8",
    )
    (root / "latex" / entry).write_text(
        BS + "input{front/cover}\n" + BS + f"{body_command}{{1}}{{3}}\n",
        encoding="utf-8",
    )
    for number in range(1, 4):
        (root / "latex" / "pages" / f"pages-{number:03d}.tex").write_text(
            f"% Source page: pages-{number:03d}\n"
            + BS + "begin{bookbody}\n" + BS + "begin{booktext}\n正文。\n"
            + BS + "end{booktext}\n" + BS + "end{bookbody}\n",
            encoding="utf-8",
        )
    (control / "semantic-audit.json").write_text(json.dumps({
        "owner_environments": ["bookbody", "booktext", "bookbodyalt"],
        "owner_parent_environments": {"booktext": ["bookbody"]},
        "cross_page_owner_environments": [],
        "question_owner_environments": [],
        "answer_owner_environments": [],
        "answer_media_environments": [],
    }), encoding="utf-8")
    return root


def orchestrator(project: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "orchestrate.py"), str(project), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_single_entry_with_bookinput(tmp_path):
    project = make_project(tmp_path / "a", "main.tex", BS + "bookinput")
    result = orchestrator(project, "plan", "--batch", "2")
    assert result.returncode == 0, result.stderr
    state = json.loads(
        (project / ".reconstruct-scanned-pdf-to-latex" / "dispatch.json").read_text(encoding="utf-8")
    )
    assert state["batches"]["b001-002"]["end"] == 2
    assert state["batches"]["b003-003"]["end"] == 3


def test_workbook_entry_with_bookinputpages(tmp_path):
    """形态 B：范围写在独立做题本入口里，且用另一种命令名。"""

    project = make_project(tmp_path / "b", "main-workbook.tex", BS + "bookinputpages")
    result = orchestrator(project, "plan", "--batch", "3")
    assert result.returncode == 0, result.stderr
    state = json.loads(
        (project / ".reconstruct-scanned-pdf-to-latex" / "dispatch.json").read_text(encoding="utf-8")
    )
    assert list(state["batches"]) == ["b001-003"]


def test_entry_name_is_not_hardcoded(tmp_path):
    """只有做题本入口时也要能找到范围。"""

    project = make_project(tmp_path / "c", "main-workbook.tex", BS + "bookinput")
    result = orchestrator(project, "plan", "--batch", "2")
    assert result.returncode == 0, result.stderr


def test_conflicting_declarations_are_rejected(tmp_path):
    """两个入口都声明范围说明事实重复，必须报错而不是任选一个。"""

    project = make_project(tmp_path / "d", "main.tex", BS + "bookinput")
    (project / "latex" / "main-workbook.tex").write_text(
        BS + "bookinputpages{1}{3}\n", encoding="utf-8"
    )
    result = orchestrator(project, "plan")
    assert result.returncode == 2
    assert "只能有一处" in result.stderr


def test_missing_range_is_reported_clearly(tmp_path):
    project = tmp_path / "e"
    (project / "latex").mkdir(parents=True)
    (project / "latex" / "main.tex").write_text(BS + "input{front/cover}\n", encoding="utf-8")
    result = orchestrator(project, "plan")
    assert result.returncode == 2
    assert "找不到正文范围声明" in result.stderr
