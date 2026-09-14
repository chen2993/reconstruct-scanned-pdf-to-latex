"""成品审计：整页位图与答案泄漏。"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

fitz = pytest.importorskip("fitz", reason="需要 PyMuPDF 生成测试 PDF")
PIL_Image = pytest.importorskip("PIL.Image", reason="需要 Pillow 生成测试图像")


def audit(pdf: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "audit_pdf_build.py"), str(pdf), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def text_pdf(path: Path, pages: int = 2) -> Path:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page()
        page.insert_text((72, 72), f"第 {index + 1} 页正文")
    document.save(path)
    document.close()
    return path


def raster_pdf(path: Path) -> Path:
    """A page whose visible area is one full-page bitmap."""

    image = PIL_Image.new("RGB", (400, 560), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    document = fitz.open()
    page = document.new_page(width=200, height=280)
    page.insert_image(page.rect, stream=buffer.getvalue())
    document.save(path)
    document.close()
    return path


def test_text_pdf_passes(tmp_path):
    result = audit(text_pdf(tmp_path / "text.pdf"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "成品审计通过" in result.stdout


def test_full_page_raster_is_rejected(tmp_path):
    result = audit(raster_pdf(tmp_path / "raster.pdf"))
    assert result.returncode == 1
    assert "整页位图" in result.stdout + result.stderr


def test_blank_text_pages_are_reported_but_not_fatal(tmp_path):
    # 扉页和整页图本来就没有文本层，只提示不判错
    result = audit(raster_pdf(tmp_path / "raster.pdf"), "--json")
    import json

    payload = json.loads(result.stdout)
    assert payload["blank_text_pages"] == [1]
    assert payload["ok"] is False  # 因为整页位图，而不是因为空文本页
    assert all("blank" not in failure for failure in payload["failures"])


def test_sentinel_match_ignores_latex_inserted_spaces(tmp_path):
    """LaTeX 会在中西文边界插入空格，哨兵比对必须先去掉空白。"""

    document = fitz.open()
    page = document.new_page()
    # 基座 14 号字体没有中日韩字形，因此用 ASCII 标记验证同一套去空白逻辑。
    page.insert_text((72, 72), "MARK answer-one here")
    pdf = tmp_path / "sentinels.pdf"
    document.save(pdf)
    document.close()

    sentinels = tmp_path / "sentinels.txt"
    sentinels.write_text("# 注释行\nMARKanswer-one\n", encoding="utf-8")

    result = audit(pdf, "--sentinels", sentinels)
    assert result.returncode == 1
    assert "答案哨兵" in result.stdout + result.stderr


def test_absent_sentinels_pass(tmp_path):
    pdf = text_pdf(tmp_path / "text.pdf")
    sentinels = tmp_path / "sentinels.txt"
    sentinels.write_text("绝不会出现的文本\n", encoding="utf-8")
    result = audit(pdf, "--sentinels", sentinels)
    assert result.returncode == 0, result.stdout
    assert "答案哨兵检查通过" in result.stdout


def test_mixed_paper_sizes_are_reported(tmp_path):
    document = fitz.open()
    document.new_page(width=200, height=280)
    document.new_page(width=300, height=280)
    pdf = tmp_path / "mixed.pdf"
    document.save(pdf)
    document.close()
    result = audit(pdf)
    assert result.returncode == 0
    assert "多种纸型" in result.stdout


def test_missing_sentinel_file_is_a_usage_error(tmp_path):
    pdf = text_pdf(tmp_path / "text.pdf")
    result = audit(pdf, "--sentinels", tmp_path / "absent.txt")
    assert result.returncode == 2
    assert "哨兵文件不存在" in result.stderr
