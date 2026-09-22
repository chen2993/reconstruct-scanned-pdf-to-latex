"""部署工具：运行时探测、联接的创建、过期副本归档与安全移除。"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

from conftest import REPO

TOOL = REPO / "tools" / "deploy_skill.py"

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
    assert tool.describe(missing) == "缺失"

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    tool.create_junction(link, target)
    assert tool.describe(link).startswith("联接到其它位置")

    plain = tmp_path / "plain"
    plain.mkdir()
    assert tool.describe(plain).startswith("实体副本")


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

    tool.remove_link(link)
    assert not link.exists()
    # 目标目录必须完好：删除联接不等于删除内容
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_remove_refuses_a_real_directory(tool, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "data.txt").write_text("important", encoding="utf-8")
    with pytest.raises(RuntimeError, match="拒绝删除实体目录"):
        tool.remove_link(real)
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
    for runtime in ("codex", "claude", "dsh", "kimi"):
        assert runtime in result.stdout, runtime


def test_default_targets_are_the_four_primary_runtimes(tool):
    """默认只部署到 4 个主用运行时，不把技能散落到一堆不用的目录。"""

    assert tool.PRIMARY_RUNTIMES == ("codex", "claude", "dsh", "kimi")


def test_runtime_roots_use_each_tool_convention(tool):
    """每个运行时的技能根目录要按各自约定解析，不能一律套 skills/。"""

    roots = {name: root for name, root, _ in tool.runtime_roots()}
    if "kimi" in roots:
        # Kimi Code 的用户级技能目录是 ~/.kimi-code/skills/，不是厂商插件目录
        assert roots["kimi"].parts[-2:] == (".kimi-code", "skills")
        assert "plugins" not in roots["kimi"].parts
    for name in ("codex", "claude", "dsh"):
        assert name in roots, name
        assert roots[name].parts[-2] in {".codex", ".claude", ".dsh"}


def test_same_content_detects_a_stale_copy(tool, tmp_path):
    """过期判定要能看出差异，否则旧副本会被当成已部署而跳过。"""

    fresh = tmp_path / "fresh"
    (fresh / "scripts").mkdir(parents=True)
    (fresh / "SKILL.md").write_text(
        (REPO / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    for item in (REPO / "scripts").rglob("*.py"):
        if "__pycache__" in item.parts:
            continue
        target = fresh / "scripts" / item.relative_to(REPO / "scripts")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.read_bytes())
    assert tool.same_content(fresh) is True

    # 少一个脚本就应判定为过期
    stale = tmp_path / "stale"
    shutil.copytree(fresh, stale)
    next((stale / "scripts").glob("*.py")).unlink()
    assert tool.same_content(stale) is False


def test_archive_moves_the_copy_out_of_the_skill_directory(tool, tmp_path, monkeypatch):
    """归档必须移出技能目录：原地改名仍会被运行时的 **/SKILL.md 扫描当成技能。"""

    monkeypatch.setattr(tool, "home", lambda: tmp_path)
    skill_dir = tmp_path / "skills"
    stale = skill_dir / "some-skill"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("old", encoding="utf-8")

    archived = tool.archive_stale_copy(stale)
    assert not stale.exists()
    assert archived.is_file() is False and archived.is_dir()
    assert (archived / "SKILL.md").read_text(encoding="utf-8") == "old"
    # 归档目录必须落在技能目录之外，避免被递归扫描到
    assert skill_dir not in archived.parents
    assert not list(skill_dir.rglob("SKILL.md"))


def test_unknown_runtime_is_rejected(tmp_path):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOL), "--only", "not-a-runtime"],
        capture_output=True, text=True, encoding="utf-8", cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "未知或本机不存在" in result.stderr
