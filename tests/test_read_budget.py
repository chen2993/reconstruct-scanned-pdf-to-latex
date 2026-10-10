"""读图预算：由 crop_page.py 强制，超限拒绝裁剪。

超预算在真实项目里把上下文烧光、任务中途崩溃，所以它是硬边界而不是提醒。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

PIL_Image = pytest.importorskip("PIL.Image", reason="需要 Pillow 生成测试页图")

CROP = SCRIPTS / "crop_page.py"
BUDGET = SCRIPTS / "read_budget.py"


def make_project(root: Path) -> Path:
    control = root / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    image = PIL_Image.new("L", (1200, 1800), 255)
    image.save(control / "pages-013.png", dpi=(600, 600))
    image.close()
    return root


def crop(project: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(CROP), str(project), "pages-013", *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def budget(project: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(BUDGET), str(project), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def ledger(project: Path) -> dict:
    path = project / ".reconstruct-scanned-pdf-to-latex" / "read-budget.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_cropping_charges_the_budget(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(project, "tmp/c1.png", "--band", "1/4")
    assert result.returncode == 0, result.stderr
    assert "读图预算 1/10" in result.stdout
    assert ledger(project)["pages"]["pages-013"]["count"] == 1


def test_overview_is_free(tmp_path):
    """总览是定位手段，应当鼓励使用，所以不占预算。"""

    project = make_project(tmp_path / "book")
    for index in range(3):
        result = crop(project, f"tmp/o{index}.png", "--overview")
        assert result.returncode == 0, result.stderr
        assert "读图预算" not in result.stdout
    # 总览免费：连账本都不该被创建
    assert not (project / ".reconstruct-scanned-pdf-to-latex" / "read-budget.json").exists()


def test_budget_exhaustion_refuses_cropping(tmp_path):
    project = make_project(tmp_path / "book")
    for index in range(10):
        assert crop(project, f"tmp/c{index}.png", "--band", "1/4").returncode == 0
    # 第十一次必须被拒绝，并且是可读错误而不是 traceback
    blocked = crop(project, "tmp/c10.png", "--band", "1/4")
    assert blocked.returncode == 2
    assert "预算已用尽" in blocked.stderr
    assert "Traceback" not in blocked.stderr
    assert not (project / "tmp" / "c10.png").exists()


def test_reset_budget_raises_the_limit(tmp_path):
    project = make_project(tmp_path / "book")
    for index in range(10):
        crop(project, f"tmp/c{index}.png", "--band", "1/4")
    assert crop(project, "tmp/blocked.png", "--band", "1/4").returncode == 2

    raised = crop(project, "--reset-budget", "12")
    assert raised.returncode == 0, raised.stderr
    assert ledger(project)["limit"] == 12
    assert crop(project, "tmp/c10.png", "--band", "1/4").returncode == 0


def test_minimum_budget_cannot_be_lowered(tmp_path):
    """10 是硬下限：既不能把上限设到 10 以下，旧账本里的更小值也会被抬回 10。"""

    project = make_project(tmp_path / "book")
    lowered = crop(project, "--reset-budget", "6")
    assert lowered.returncode != 0
    assert "最低额度 10" in lowered.stderr
    assert "Traceback" not in lowered.stderr

    # 手工写一个历史遗留的 6，读取时必须被抬到 MIN_LIMIT。
    ledger_path = project / ".reconstruct-scanned-pdf-to-latex" / "read-budget.json"
    ledger_path.write_text(
        json.dumps({"limit": 6, "pages": {}}, ensure_ascii=False), encoding="utf-8"
    )
    assert crop(project, "tmp/c1.png", "--band", "1/4").returncode == 0
    assert ledger(project)["limit"] == 10
    assert crop(project, "--show-budget").returncode == 0


def test_show_budget_reports_without_cropping(tmp_path):
    project = make_project(tmp_path / "book")
    crop(project, "tmp/c1.png", "--band", "1/4")
    result = crop(project, "--show-budget")
    assert result.returncode == 0, result.stderr
    assert "已读 1/10" in result.stdout
    assert "1/10" in result.stdout
    # 查余额不应计入
    assert ledger(project)["pages"]["pages-013"]["count"] == 1


def test_check_and_report_are_read_only(tmp_path):
    project = make_project(tmp_path / "book")
    crop(project, "tmp/c1.png", "--band", "1/4")
    crop(project, "tmp/c2.png", "--band", "2/4")

    checked = budget(project, "check", "pages-013")
    assert checked.returncode == 0
    assert "已读 2/10" in checked.stdout
    reported = budget(project, "report")
    assert reported.returncode == 0
    assert "pages-013  2/10" in reported.stdout
    assert ledger(project)["pages"]["pages-013"]["count"] == 2


def test_report_flags_exhausted_pages(tmp_path):
    project = make_project(tmp_path / "book")
    for index in range(10):
        crop(project, f"tmp/c{index}.png", "--band", "1/4")
    reported = budget(project, "report")
    assert reported.returncode == 1
    assert "已用尽" in reported.stdout


def test_each_page_has_its_own_budget(tmp_path):
    project = make_project(tmp_path / "book")
    control = project / ".reconstruct-scanned-pdf-to-latex"
    image = PIL_Image.new("L", (1200, 1800), 255)
    image.save(control / "pages-014.png", dpi=(600, 600))
    image.close()

    for index in range(10):
        assert crop(project, f"tmp/a{index}.png", "--band", "1/4").returncode == 0
    assert crop(project, "tmp/a10.png", "--band", "1/4").returncode == 2

    other = subprocess.run(
        [sys.executable, "-X", "utf8", str(CROP), str(project), "pages-014", "tmp/b1.png", "--band", "1/4"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert other.returncode == 0, other.stderr
    assert "读图预算 1/10" in other.stdout
