"""参考类文件的契约回归：纸型、书签、答案隔离。

这些用例来自真实端到端演练中发现的缺陷，因此用真实编译而不是文本断言：

* ``original`` profile 曾经无法构建（类加载时就要求原书尺寸）；
* 做题本曾经把前置/后置模块整体隐藏，导致只剩 1 页且缺少 ``书末页`` 书签；
* 纸型 profile 曾被放在 ``\\begin{document}`` 之后应用，``geometry`` 静默忽略，
  所有做题本都退回默认纸张；
* 做题本必须隔离答案，完整书必须保留答案，跨页题目只能产生一个答题区。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BS = chr(92)

pytestmark = pytest.mark.skipif(
    shutil.which("latexmk") is None and not Path(r"D:\texlive\2026\bin\windows\latexmk.exe").is_file(),
    reason="需要 XeLaTeX/latexmk 才能验证类文件契约",
)

BOOKMARKS = ("封面", "前言", "献词", "目录", "书末页")
MARKERS = ("题干一", "答案一", "跨页题干", "跨页答案", "习题一", "习题解答")

PAGE_ONE = (
    "% Source page: pages-001\n"
    + BS + "begin{bookbody}\n"
    + BS + "begin{booktext}\n正文第一页。\n" + BS + "end{booktext}\n"
    + BS + "end{bookbody}\n"
    + BS + "begin{bookexample}\nMARK题干一。\n"
    + BS + "begin{bookanswer}\nMARK答案一。\n" + BS + "end{bookanswer}\n"
    + BS + "end{bookexample}\n"
    + BS + "begin{bookexample}\n跨页题干，MARK跨页题干。\n"
)

PAGE_TWO = (
    "% Source page: pages-002\n"
    + BS + "begin{bookanswer}\nMARK跨页答案。\n" + BS + "end{bookanswer}\n"
    + BS + "end{bookexample}\n"
    + BS + "begin{bookexercise}\nMARK习题一。\n"
    + BS + "begin{booksolution}\nMARK习题解答。\n" + BS + "end{booksolution}\n"
    + BS + "end{bookexercise}\n"
    + BS + "begin{bookbody}\n"
    + BS + "begin{booktext}\n正文第二页。\n" + BS + "end{booktext}\n"
    + BS + "end{bookbody}\n"
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture(scope="module")
def latex_env() -> dict:
    environment = dict(os.environ)
    texlive = r"D:\texlive\2026\bin\windows"
    if Path(texlive).is_dir() and texlive not in environment.get("PATH", ""):
        environment["PATH"] = texlive + os.pathsep + environment["PATH"]
    return environment


@pytest.fixture(scope="module")
def book(tmp_path_factory, latex_env) -> Path:
    """A minimal but structurally real book that can be built for any target."""

    work = tmp_path_factory.mktemp("book")
    class_source = (REPO / "template" / "base.cls").read_text(encoding="utf-8")
    class_source = class_source.replace(BS + "ProvidesClass{base}", BS + "ProvidesClass{probe}")
    # The confirmed source paper size, declared from the class preamble.
    class_source += "\n" + BS + "booksetoriginalpagesize{185mm}{260mm}\n"
    write(work / "probe.cls", class_source)

    for name, title, key in (
        ("cover", "封面", "cover"),
        ("preface", "前言", "preface"),
        ("dedication", "献词", "dedication"),
    ):
        write(
            work / "front" / f"{name}.tex",
            BS + f"bookbookmarkmodule{{{title}}}{{{key}}}\n"
            + BS + "begin{bookfrontmatterblock}\n" + title + "内容\n"
            + BS + "end{bookfrontmatterblock}\n",
        )
    write(
        work / "front" / "toc.tex",
        BS + "bookbookmarkmodule{目录}{toc}\n" + BS + "bookmaketoc\n",
    )
    write(
        work / "back" / "backmatter.tex",
        BS + "bookbookmarkmodule{书末页}{backmatter}\n"
        + BS + "begin{bookbackmatterblock}\n书末页内容\n"
        + BS + "end{bookbackmatterblock}\n",
    )
    write(work / "pages" / "pages-001.tex", PAGE_ONE)
    write(work / "pages" / "pages-002.tex", PAGE_TWO)
    write(
        work / "main.tex",
        BS + "providecommand{" + BS + "BookBuildOptions}{book,print}\n"
        + BS + "edef" + BS + "BookApplyBuildOptions{" + BS + "noexpand" + BS
        + "PassOptionsToClass{" + BS + "BookBuildOptions}{probe}}\n"
        + BS + "BookApplyBuildOptions\n"
        + BS + "let" + BS + "BookApplyBuildOptions" + BS + "relax\n"
        + BS + "documentclass{probe}\n"
        + BS + "begin{document}\n"
        + BS + "input{front/cover}\n"
        + BS + "input{front/preface}\n"
        + BS + "input{front/dedication}\n"
        + BS + "input{front/toc}\n"
        + BS + "bookinput{1}{2}\n"
        + BS + "input{back/backmatter}\n"
        + BS + "end{document}\n",
    )
    return work


def build(book: Path, name: str, options: str, environment: dict) -> Path:
    """Compile one target and return its PDF, failing on a LaTeX error."""

    out = book / "out"
    out.mkdir(parents=True, exist_ok=True)
    write(out / "driver.tex", BS + f"def{BS}BookBuildOptions{{{options}}}\n" + BS + "input{main.tex}\n")
    result = subprocess.run(
        [
            "latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
            "-file-line-error", "-no-shell-escape",
            f"-outdir={out}", f"-jobname={name}", str(out / "driver.tex"),
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=book, env=environment,
    )
    pdf = out / f"{name}.pdf"
    assert pdf.is_file(), f"{options} 未生成 PDF:\n{result.stdout[-3000:]}"
    return pdf


def inspect(pdf: Path) -> tuple[list[str], list[str], float, float]:
    import fitz

    document = fitz.open(pdf)
    text = "".join(page.get_text() for page in document)
    bookmarks = [entry[1] for entry in document.get_toc()]
    rect = document.load_page(0).rect
    size = (rect.width, rect.height)
    document.close()
    return bookmarks, [mark for mark in MARKERS if mark in text], *size


def test_complete_book_keeps_answers_and_bookmarks(book, latex_env):
    bookmarks, marks, _, _ = inspect(build(book, "book", "book,print", latex_env))
    assert bookmarks == list(BOOKMARKS)
    assert marks == list(MARKERS)


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ("workbook,examples,original,print", ["题干一", "跨页题干"]),
        ("workbook,exercises,original,print", ["习题一"]),
        ("workbook,all,original,print", ["题干一", "跨页题干", "习题一"]),
    ],
)
def test_workbook_isolates_answers(book, latex_env, options, expected):
    bookmarks, marks, _, _ = inspect(build(book, options.split(",")[1], options, latex_env))
    # 每个目标都复用同一组前后置模块和同一组必需书签
    assert bookmarks == list(BOOKMARKS)
    assert marks == expected


@pytest.mark.parametrize(
    ("profile", "size_mm"),
    [
        ("original", (185, 260)),
        ("pad11", (280, 193)),
        ("pad13", (280, 210)),
        ("a4", (210, 297)),
    ],
)
def test_workbook_profiles_change_the_media_box(book, latex_env, profile, size_mm):
    options = f"workbook,examples,{profile},print"
    _, _, width, height = inspect(build(book, f"wb-{profile}", options, latex_env))
    expected_width, expected_height = (value / 25.4 * 72 for value in size_mm)
    assert abs(width - expected_width) < 2, f"{profile} 宽度不符: {width}"
    assert abs(height - expected_height) < 2, f"{profile} 高度不符: {height}"


def test_missing_original_paper_size_fails_loudly(book, latex_env, tmp_path):
    """没有确认原书尺寸时必须报错，不能悄悄使用默认纸张。"""

    broken = tmp_path / "broken"
    shutil.copytree(book, broken, ignore=shutil.ignore_patterns("out"))
    class_path = broken / "probe.cls"
    class_path.write_text(
        class_path.read_text(encoding="utf-8").replace(
            BS + "booksetoriginalpagesize{185mm}{260mm}", ""
        ),
        encoding="utf-8",
    )
    out = broken / "out"
    out.mkdir()
    write(out / "driver.tex", BS + "def" + BS + "BookBuildOptions{book,print}\n" + BS + "input{main.tex}\n")
    result = subprocess.run(
        [
            "latexmk", "-xelatex", "-interaction=nonstopmode",
            f"-outdir={out}", "-jobname=broken", str(out / "driver.tex"),
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=broken, env=latex_env,
    )
    assert "Original paper size is not configured" in (result.stdout + result.stderr)
