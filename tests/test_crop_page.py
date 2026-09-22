"""页图读取工具：总览、横带、区域裁剪与输出位置约束。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

PIL_Image = pytest.importorskip("PIL.Image", reason="需要 Pillow 生成测试页图")

PAGE_WIDTH = 4000
PAGE_HEIGHT = 6000


def make_project(root: Path, dpi: int = 600) -> Path:
    """A project with one 600 dpi-style page: top half light, bottom half dark."""

    control = root / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    image = PIL_Image.new("L", (PAGE_WIDTH, PAGE_HEIGHT), 255)
    for y in range(PAGE_HEIGHT // 2, PAGE_HEIGHT):
        for x in range(0, PAGE_WIDTH, 4):
            image.putpixel((x, y), 200)
    image.save(control / "pages-013.png", dpi=(dpi, dpi))
    image.close()
    return root


def crop(project: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "crop_page.py"), str(project), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_overview_shrinks_the_whole_page(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/over.png", "--overview")
    assert result.returncode == 0, result.stderr
    with PIL_Image.open(project / "tmp" / "over.png") as image:
        assert image.width == 1100
        assert image.height == round(PAGE_HEIGHT * 1100 / PAGE_WIDTH)
    assert "不要用它读公式" in result.stdout


def test_band_keeps_full_width(tmp_path):
    """横带只切高度：这是它的用途（保留整行版式），也是它不能提高清晰度的原因。"""

    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/b2.png", "--band", "2/2")
    assert result.returncode == 0, result.stderr
    with PIL_Image.open(project / "tmp" / "b2.png") as image:
        assert image.width == PAGE_WIDTH
        assert image.height == PAGE_HEIGHT // 2
        assert image.getpixel((PAGE_WIDTH // 2, PAGE_HEIGHT // 4)) == 200
    assert "会被缩小" in result.stdout


def test_region_narrows_the_width(tmp_path):
    """窄区域不会被读取环节缩小，等效 dpi 保持源值——这才是看清公式的方式。"""

    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/z.png", "--region", "0.10,0.30,0.30,0.40")
    assert result.returncode == 0, result.stderr
    with PIL_Image.open(project / "tmp" / "z.png") as image:
        assert image.width == round(PAGE_WIDTH * 0.20)
    assert "等效约 600 dpi" in result.stdout
    assert "会被缩小" not in result.stdout


def test_wide_region_warns_about_reader_shrinking(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/wide.png", "--region", "0,0.30,1,0.40")
    assert result.returncode == 0, result.stderr
    assert "会被缩小" in result.stdout


def test_json_reports_the_numbers_an_agent_needs(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/z.png", "--region", "0.1,0.3,0.3,0.4", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "region"
    assert payload["page_px"] == [PAGE_WIDTH, PAGE_HEIGHT]
    assert payload["output_px"][0] == round(PAGE_WIDTH * 0.20)
    assert payload["source_dpi"] == 600.0
    assert payload["effective_dpi"] == 600.0
    assert payload["will_be_shrunk_by_reader"] is False


def test_scale_is_applied_after_cropping(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(
        project, "pages-013", "tmp/s.png",
        "--region", "0,0,1,0.5", "--scale", "0.25",
    )
    assert result.returncode == 0, result.stderr
    with PIL_Image.open(project / "tmp" / "s.png") as image:
        assert image.size == (PAGE_WIDTH // 4, PAGE_HEIGHT // 8)


def test_output_outside_tmp_is_rejected(tmp_path):
    """裁图只是临时视觉证据，不允许写进交付树。"""

    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "latex/pages/leak.png", "--overview")
    assert result.returncode == 2
    assert "只能写入项目 tmp/" in result.stderr
    assert not (project / "latex" / "pages" / "leak.png").exists()


def test_absolute_output_outside_project_is_rejected(tmp_path):
    project = make_project(tmp_path / "book")
    outside = tmp_path / "elsewhere" / "x.png"
    result = crop(project, "pages-013", outside, "--overview")
    assert result.returncode == 2
    assert not outside.exists()


def test_missing_page_reports_clearly(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(project, "pages-999", "tmp/x.png", "--overview")
    assert result.returncode == 2
    assert "找不到页面 PNG" in result.stderr


def test_bad_page_identifier_is_rejected(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(project, "page-013", "tmp/x.png", "--overview")
    assert result.returncode == 2
    assert "front-/pages-/back-" in result.stderr


def test_selectors_are_mutually_exclusive(tmp_path):
    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/x.png", "--band", "1/2", "--region", "0,0,1,0.5")
    assert result.returncode == 2
    assert "只能用一个" in result.stderr
    result = crop(project, "pages-013", "tmp/x.png", "--overview", "--band", "1/2")
    assert result.returncode == 2


@pytest.mark.parametrize("value", ["0/3", "4/3", "x/y", "1"])
def test_invalid_band_is_rejected(tmp_path, value):
    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/x.png", "--band", value)
    assert result.returncode == 2


@pytest.mark.parametrize("value", ["0,0,1", "0,0,1,1.5", "0.9,0,0.1,1"])
def test_invalid_region_is_rejected(tmp_path, value):
    project = make_project(tmp_path / "book")
    result = crop(project, "pages-013", "tmp/x.png", "--region", value)
    assert result.returncode == 2


def test_missing_dpi_metadata_is_reported_not_invented(tmp_path):
    """没有 dpi 元数据时如实说明，不编一个看起来精确的等效分辨率。"""

    project = tmp_path / "book"
    control = project / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True)
    (project / "tmp").mkdir()
    image = PIL_Image.new("L", (1200, 1800), 255)
    image.save(control / "front-001.png")  # 不写 dpi
    image.close()
    result = crop(project, "front-001", "tmp/x.png", "--overview")
    assert result.returncode == 0, result.stderr
    assert "没有 dpi 元数据" in result.stdout
    assert "等效约" not in result.stdout
