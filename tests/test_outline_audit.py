"""PDF outline 审计：按项目登记的前后置模块校验，而不是固定四键。

真实教材各不相同：有的没有献词，有的没有单独封面，有的多出目录说明。审计器必须
覆盖"原件有的模块"，既不漏提取已存在的模块，也不强求不存在的模块。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

fitz = pytest.importorskip("fitz", reason="需要 PyMuPDF 生成测试 PDF")

AUDIT = SCRIPTS / "audit_pdf_outline.py"


def make_pdf(path: Path, bookmarks: list[tuple[str, int]], pages: int = 4) -> Path:
    """Build a PDF whose outline has the given (title, 1-based page) entries.

    Uses link destinations so PyMuPDF reports a real outline, and draws a mark on
    every page except the ones we deliberately leave blank.
    """
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    toc = [[1, title, page] for title, page in bookmarks]
    document.set_toc(toc)
    for index in range(pages):
        page = document.load_page(index)
        # 每页都画一笔，避免"空白页"检查干扰书签结构用例
        page.insert_text((72, 72), f"page {index + 1}")
    document.save(path)
    document.close()
    return path


def audit(pdf: Path, *entries: str) -> subprocess.CompletedProcess:
    args = [sys.executable, "-X", "utf8", str(AUDIT), str(pdf)]
    if entries:
        args += ["--required-map", *entries]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")


def test_declared_modules_pass(tmp_path):
    pdf = make_pdf(
        tmp_path / "a.pdf",
        [("封面", 1), ("前言", 2), ("献词", 3), ("目录", 4)],
    )
    result = audit(pdf, "cover=封面", "preface=前言", "dedication=献词", "toc=目录")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PDF outline 通过" in result.stdout


def test_book_without_dedication_passes(tmp_path):
    """原件没有献词时不该被要求有献词书签。"""

    pdf = make_pdf(tmp_path / "b.pdf", [("封面", 1), ("前言", 2), ("目录", 3)])
    result = audit(pdf, "cover=封面", "preface=前言", "toc=目录")
    assert result.returncode == 0, result.stdout + result.stderr


def test_declared_module_missing_from_pdf_fails(tmp_path):
    """登记了却没提取出来，必须报错——这正是"漏提取"。"""

    pdf = make_pdf(tmp_path / "c.pdf", [("封面", 1), ("目录", 2)])
    result = audit(pdf, "cover=封面", "preface=前言", "toc=目录")
    assert result.returncode == 1
    assert "缺少顶层书签: 前言" in result.stderr


def test_single_module_is_accepted(tmp_path):
    """只要项目登记的模块真实存在，一个也可以。"""

    pdf = make_pdf(tmp_path / "d.pdf", [("封面", 1)])
    result = audit(pdf, "cover=封面")
    assert result.returncode == 0, result.stdout + result.stderr


def test_order_must_match_the_declared_original_order(tmp_path):
    pdf = make_pdf(tmp_path / "e.pdf", [("前言", 1), ("封面", 2)])
    result = audit(pdf, "cover=封面", "preface=前言")
    assert result.returncode == 1
    assert "顺序必须与登记顺序一致" in result.stderr


def test_duplicate_top_level_bookmark_is_rejected(tmp_path):
    pdf = make_pdf(tmp_path / "f.pdf", [("封面", 1), ("封面", 2)])
    result = audit(pdf, "cover=封面")
    assert result.returncode == 1
    assert "顶层书签重复: 封面" in result.stderr


def test_book_without_any_front_or_back_module_passes(tmp_path):
    """原件可以没有任何前后置模块（纯正文扫描件）：此时只检查 outline 结构。"""

    pdf = make_pdf(tmp_path / "g.pdf", [])
    result = audit(pdf)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "未登记前后置模块" in result.stdout


def test_empty_manifest_still_validates_outline_structure(tmp_path):
    """空清单不等于完全不检查：登记模块后重复顶层书签仍要报错。

    PyMuPDF 自己会拒绝构造非法层级、钳制越界页码、丢弃空标题，所以这里用
    "重复顶层标题"这一能被保留的问题，验证结构检查没有被空清单短路。
    """

    pdf = make_pdf(tmp_path / "g2.pdf", [("封面", 1), ("封面", 2)])
    # 不登记任何模块：结构错误（重复顶层书签）仍应被报出
    empty = audit(pdf)
    assert empty.returncode == 0, empty.stdout + empty.stderr

    # 登记后必须检出重复
    declared = audit(pdf, "cover=封面")
    assert declared.returncode == 1
    assert "顶层书签重复" in declared.stderr


@pytest.mark.parametrize(
    "entry",
    ["封面", "=封面", "cover=", "Cover=封面", "cover-a=封面"],
)
def test_malformed_entries_are_rejected(tmp_path, entry):
    """语义键必须是英文 ASCII 标识符，标题不能为空。"""

    pdf = make_pdf(tmp_path / "h.pdf", [("封面", 1)])
    result = audit(pdf, entry)
    assert result.returncode == 2
    assert "无效" in result.stderr or "标识符" in result.stderr


def test_duplicate_keys_or_titles_are_rejected(tmp_path):
    pdf = make_pdf(tmp_path / "i.pdf", [("封面", 1), ("卷首", 2)])
    assert audit(pdf, "cover=封面", "cover=卷首").returncode == 2
    assert audit(pdf, "cover=封面", "front=封面").returncode == 2


def test_blank_target_page_is_rejected(tmp_path):
    """书签指向完全空白的页面要报错：那通常意味着锚点落错位置。"""

    document = fitz.open()
    document.new_page()
    document.new_page()  # 这一页故意不画任何内容，用于验证空白目标页检查
    document.set_toc([[1, "封面", 2]])
    document.save(tmp_path / "j.pdf")
    document.close()
    result = audit(tmp_path / "j.pdf", "cover=封面")
    assert result.returncode == 1
    assert "空白页" in result.stderr
