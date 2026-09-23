"""前后置模块的来源页覆盖审计。

原来只审计 latex/pages；前后置模块的 `%   front-001` 覆盖标记无人核对，
模块可以在没有来源标记或标记错乱的情况下通过审计。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import BS, SCRIPTS


def make_project(root: Path) -> Path:
    for part in ("latex/front", "latex/back", "latex/pages", "docs"):
        (root / part).mkdir(parents=True, exist_ok=True)
    control = root / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True, exist_ok=True)
    (root / "latex" / "main.tex").write_text(
        BS + "input{front/cover}\n" + BS + "bookinput{1}{1}\n", encoding="utf-8"
    )
    (root / "latex" / "pages" / "pages-001.tex").write_text(
        "% Source page: pages-001\n", encoding="utf-8"
    )
    return root


def write_module(project: Path, section: str, name: str, markers: list[str]) -> None:
    lines = ["% Generated logical module stub; replace with reconstructed content.",
             f"% Module: {name}", "% Source pages:"]
    lines += [f"%   {marker}" for marker in markers]
    (project / "latex" / section / f"{name}.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def audit(project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "audit_provenance.py"), str(project)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_wellformed_modules_pass(tmp_path):
    project = make_project(tmp_path / "book")
    write_module(project, "front", "cover", ["front-001"])
    write_module(project, "front", "preface", ["front-002", "front-003"])
    write_module(project, "back", "afterword", ["back-001"])
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_module_without_coverage_marker_fails(tmp_path):
    """模块不可能凭空出现：没有覆盖标记就无法追溯它覆盖哪些源页。"""

    project = make_project(tmp_path / "book")
    (project / "latex" / "front" / "cover.tex").write_text(
        "% Generated logical module stub;\n% Module: cover\n", encoding="utf-8"
    )
    result = audit(project)
    assert result.returncode == 1
    assert "missing_module_coverage" in result.stdout


def test_section_mismatch_fails(tmp_path):
    """front/ 下的模块不能声明 back- 标识。"""

    project = make_project(tmp_path / "book")
    write_module(project, "front", "cover", ["back-001"])
    result = audit(project)
    assert result.returncode == 1
    assert "module_marker_section_mismatch" in result.stdout


def test_overlapping_coverage_fails(tmp_path):
    """同一最终标识只能被一个模块声明，否则来源归属歧义。"""

    project = make_project(tmp_path / "book")
    write_module(project, "front", "cover", ["front-001"])
    write_module(project, "front", "preface", ["front-001"])
    result = audit(project)
    assert result.returncode == 1
    assert "module_coverage_overlap" in result.stdout


def test_duplicate_and_order_fail(tmp_path):
    project = make_project(tmp_path / "book")
    write_module(project, "front", "cover", ["front-002", "front-002"])
    result = audit(project)
    assert result.returncode == 1
    assert "module_marker_duplicate" in result.stdout

    other = make_project(tmp_path / "book2")
    write_module(other, "front", "cover", ["front-003", "front-001"])
    result = audit(other)
    assert result.returncode == 1
    assert "module_marker_out_of_order" in result.stdout


def test_page_numbered_module_filename_fails(tmp_path):
    project = make_project(tmp_path / "book")
    (project / "latex" / "front" / "front-001.tex").write_text(
        "%   front-001\n", encoding="utf-8"
    )
    result = audit(project)
    assert result.returncode == 1
    assert "bad_module_filename" in result.stdout
