"""页范围子集导出：供没有页范围参数的候选工具使用。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import SCRIPTS


SCRIPT = SCRIPTS / "extract_page_range.py"

fitz = pytest.importorskip("pymupdf", reason="需要 PyMuPDF 生成与校验测试 PDF")


def make_pdf(path, pages: int = 5):
    document = fitz.open()
    for index in range(1, pages + 1):
        page = document.new_page(width=300, height=400)
        page.insert_text((40, 60), f"page {index}", fontsize=14, fontname="helv")
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()
    return path


def make_project(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    return root


def run(project, source, *args):
    return subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(SCRIPT),
            str(project),
            str(source),
            *map(str, args),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def page_texts(path):
    document = fitz.open(path)
    try:
        return [document[i].get_text().strip() for i in range(document.page_count)]
    finally:
        document.close()


def test_extracts_requested_pages(tmp_path):
    project = make_project(tmp_path / "project")
    source = make_pdf(tmp_path / "src.pdf")
    result = run(project, source, "--pages", "2-4", "--output", "tmp/sub.pdf")
    assert result.returncode == 0, result.stderr
    assert page_texts(project / "tmp" / "sub.pdf") == ["page 2", "page 3", "page 4"]


def test_comma_separated_and_single_pages(tmp_path):
    project = make_project(tmp_path / "project")
    source = make_pdf(tmp_path / "src.pdf")
    result = run(project, source, "--pages", "1,3,5", "--output", "tmp/sub.pdf")
    assert result.returncode == 0, result.stderr
    assert page_texts(project / "tmp" / "sub.pdf") == ["page 1", "page 3", "page 5"]


def test_does_not_modify_source(tmp_path):
    project = make_project(tmp_path / "project")
    source = make_pdf(tmp_path / "src.pdf")
    before = source.read_bytes()
    assert run(project, source, "--pages", "1-2", "--output", "tmp/sub.pdf").returncode == 0
    assert source.read_bytes() == before
    assert page_texts(source) == [f"page {i}" for i in range(1, 6)]


def test_rejects_output_outside_tmp(tmp_path):
    project = make_project(tmp_path / "project")
    source = make_pdf(tmp_path / "src.pdf")
    result = run(project, source, "--pages", "1", "--output", "latex/bad.pdf")
    assert result.returncode == 2
    assert "tmp/" in result.stderr
    assert not (project / "latex" / "bad.pdf").exists()


def test_rejects_page_beyond_document(tmp_path):
    project = make_project(tmp_path / "project")
    source = make_pdf(tmp_path / "src.pdf", pages=3)
    result = run(project, source, "--pages", "4", "--output", "tmp/sub.pdf")
    assert result.returncode == 2
    assert "超出" in result.stderr
    assert not (project / "tmp" / "sub.pdf").exists()


@pytest.mark.parametrize("value", ("0", "3-1", "a", "1-", "", "1,,2"))
def test_rejects_malformed_ranges(tmp_path, value):
    project = make_project(tmp_path / "project")
    source = make_pdf(tmp_path / "src.pdf")
    result = run(project, source, "--pages", value, "--output", "tmp/sub.pdf")
    assert result.returncode == 2
    assert "页范围" in result.stderr


def test_rejects_overwriting_source(tmp_path):
    project = make_project(tmp_path / "project")
    source = make_pdf(project / "tmp" / "src.pdf")
    result = run(project, source, "--pages", "1", "--output", "tmp/src.pdf")
    assert result.returncode == 2
    assert "覆盖" in result.stderr
    assert page_texts(source) == [f"page {i}" for i in range(1, 6)]
