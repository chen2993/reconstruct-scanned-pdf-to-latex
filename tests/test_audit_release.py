"""发布前泄漏审计：扫描件/页图不得进入版本控制。

扫描件进了 Git 历史就无法真正移除，等于既成事实的再分发，所以这一步必须是
可重复的脚本检查，而不是人工核对。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

AUDIT = SCRIPTS / "audit_release.py"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="需要 git 才能验证版本控制状态"
)


def git(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    return root


def audit(project: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(AUDIT), str(project), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def write_release_files(project: Path) -> None:
    (project / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (project / "NOTICE.md").write_text("# Notice\n", encoding="utf-8")
    (project / ".gitignore").write_text(
        "/reference/\n/references/\n/sources/\n/dist/\n/tmp/\n"
        "/.reconstruct-scanned-pdf-to-latex/*.png\n",
        encoding="utf-8",
    )


def test_clean_repo_passes(tmp_path):
    project = init_repo(tmp_path / "book")
    write_release_files(project)
    (project / "main.tex").write_text("x", encoding="utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-m", "init")

    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "发布前审计通过" in result.stdout


def test_tracked_page_image_fails(tmp_path):
    """页图被跟踪 = 原书扫描进入版本控制，必须报错。"""

    project = init_repo(tmp_path / "book")
    write_release_files(project)
    control = project / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True)
    (control / "pages-001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    git(project, "add", "-A", "-f")
    git(project, "commit", "-m", "init")

    result = audit(project)
    assert result.returncode == 1
    assert "pages-001.png" in result.stderr
    assert "跟踪着" in result.stderr


def test_tracked_source_pdf_fails(tmp_path):
    project = init_repo(tmp_path / "book")
    write_release_files(project)
    (project / "scan.pdf").write_bytes(b"%PDF-1.4\n")
    git(project, "add", "-A", "-f")
    git(project, "commit", "-m", "init")

    result = audit(project)
    assert result.returncode == 1
    assert "scan.pdf" in result.stderr


def test_tracked_local_input_dir_fails(tmp_path):
    project = init_repo(tmp_path / "book")
    write_release_files(project)
    reference = project / "reference"
    reference.mkdir()
    (reference / "original.txt").write_text("x", encoding="utf-8")
    git(project, "add", "-A", "-f")
    git(project, "commit", "-m", "init")

    result = audit(project)
    assert result.returncode == 1
    assert "本地 QA 输入" in result.stderr


def test_historical_scan_is_reported_even_after_removal(tmp_path):
    """历史里出现过就仍可恢复，必须提示——这正是"删除不够"的原因。"""

    project = init_repo(tmp_path / "book")
    write_release_files(project)
    control = project / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True)
    image = control / "pages-001.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    git(project, "add", "-A", "-f")
    git(project, "commit", "-m", "with scan")
    image.unlink()
    git(project, "add", "-A")
    git(project, "commit", "-m", "remove scan")

    result = audit(project)
    # 当前已不跟踪 -> 不算硬失败
    assert result.returncode == 0, result.stdout + result.stderr
    assert "历史中曾出现过" in result.stderr


def test_missing_gitignore_entries_fail(tmp_path):
    project = init_repo(tmp_path / "book")
    (project / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (project / "NOTICE.md").write_text("# Notice\n", encoding="utf-8")
    (project / ".gitignore").write_text("/tmp/\n", encoding="utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-m", "init")

    result = audit(project)
    assert result.returncode == 1
    assert "gitignore 未覆盖必需路径" in result.stderr


def test_missing_legal_files_fail(tmp_path):
    project = init_repo(tmp_path / "book")
    (project / ".gitignore").write_text(
        "/reference/\n/references/\n/sources/\n/dist/\n/tmp/\n", encoding="utf-8"
    )
    git(project, "add", "-A")
    git(project, "commit", "-m", "init")

    result = audit(project)
    assert result.returncode == 1
    assert "缺少仓库级法律文件" in result.stderr
    assert "LICENSE" in result.stderr


def test_json_report_shape(tmp_path):
    project = init_repo(tmp_path / "book")
    write_release_files(project)
    git(project, "add", "-A")
    git(project, "commit", "-m", "init")

    result = audit(project, "--json")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["tracked_scans"] == []
    assert payload["missing_files"] == []


def test_not_a_git_repo_is_usage_error(tmp_path):
    project = tmp_path / "plain"
    project.mkdir()
    result = audit(project)
    assert result.returncode == 2
    assert "不是 Git 工作树" in result.stderr
