"""部署工具：联接的创建、识别与安全移除。"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

from conftest import REPO

TOOL = REPO / "tools" / "deploy_skill.py"

pytest.importorskip("pytest")

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="目录联接（junction）只在 Windows 上验证"
)


def load():
    spec = importlib.util.spec_from_file_location("deploy_skill", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tool():
    return load()


def test_status_reports_missing_and_link(tool, tmp_path):
    missing = tmp_path / "absent"
    assert tool.link_state(missing) == "缺失"

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    tool.create_junction(link, target)
    assert tool.link_state(link).startswith("链接")

    plain = tmp_path / "plain"
    plain.mkdir()
    assert tool.link_state(plain) == "实体目录"


def test_link_resolves_to_the_repository(tool, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "SKILL.md").write_text("x", encoding="utf-8")
    link = tmp_path / "skills" / "reconstruct-scanned-pdf-to-latex"
    tool.create_junction(link, target)
    # 通过联接读写即读写仓库本体，这正是开发期部署要的语义
    assert (link / "SKILL.md").read_text(encoding="utf-8") == "x"
    (link / "new.txt").write_text("y", encoding="utf-8")
    assert (target / "new.txt").read_text(encoding="utf-8") == "y"


def test_remove_drops_only_the_link(tool, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "link"
    tool.create_junction(link, target)

    tool.remove_path(link)
    assert not link.exists()
    # 目标目录必须完好：删除联接不等于删除内容
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_remove_refuses_a_real_directory(tool, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "data.txt").write_text("important", encoding="utf-8")
    with pytest.raises(RuntimeError, match="拒绝删除实体目录"):
        tool.remove_path(real)
    assert (real / "data.txt").read_text(encoding="utf-8") == "important"


def test_create_refuses_to_overwrite(tool, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    occupied = tmp_path / "link"
    occupied.mkdir()
    with pytest.raises(RuntimeError, match="已存在"):
        tool.create_junction(occupied, target)


def test_cli_status_lists_both_runtimes(tmp_path):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOL), "--status"],
        capture_output=True, text=True, encoding="utf-8", cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "Codex" in result.stdout
    assert "Claude Code" in result.stdout
