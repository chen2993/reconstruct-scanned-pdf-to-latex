"""编号接口的编译回归：小问、选项、圈码都必须由 .cls 生成。

这条回归针对实测缺陷：agent 遇到小问和选择题时容易在页面源码里手打
``(1)``/``A.``。类文件若不提供可直接调用的语义接口，规则就只会停留在文档里。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BS = chr(92)

pytestmark = pytest.mark.skipif(
    shutil.which("latexmk") is None
    and not Path(r"D:\texlive\2026\bin\windows\latexmk.exe").is_file(),
    reason="需要 XeLaTeX/latexmk 才能验证编号接口",
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
def numbered_document(tmp_path_factory, latex_env) -> str:
    """编译一个覆盖全部编号接口的最小文档，返回规范化文本。"""

    work = tmp_path_factory.mktemp("numbering")
    class_source = (REPO / "template" / "base.cls").read_text(encoding="utf-8")
    class_source = class_source.replace(
        BS + "ProvidesClass{base}", BS + "ProvidesClass{probe}"
    )
    class_source += "\n" + BS + "booksetoriginalpagesize{185mm}{260mm}\n"
    write(work / "probe.cls", class_source)

    document = (
        BS + "documentclass{probe}\n"
        + BS + "begin{document}\n"
        + BS + "begin{booksubitems}\n"
        + BS + "item 甲\n"
        + BS + "item 乙\n"
        + BS + "end{booksubitems}\n"
        + "\n"
        + BS + "bookchoicesfour{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoicesfour{戊}{己}{庚}{辛}\n"
        + BS + "bookchoicesparen{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoicestwobytwo{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoicesvertical{甲}{乙}{丙}{丁}\n"
        + "\n"
        + BS + "begin{bookcircleditems}\n"
        + BS + "item 甲\n"
        + BS + "item 乙\n"
        + BS + "end{bookcircleditems}\n"
        + BS + "end{document}\n"
    )
    write(work / "main.tex", document)

    result = subprocess.run(
        [
            "latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
            "-file-line-error", "-no-shell-escape", "-outdir=out", "-jobname=numbered",
            "main.tex",
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=work, env=latex_env,
    )
    pdf = work / "out" / "numbered.pdf"
    assert pdf.is_file(), result.stdout[-3000:]

    import fitz

    handle = fitz.open(pdf)
    text = "".join(page.get_text() for page in handle)
    handle.close()
    return re.sub(r"\s+", "", text)


def test_subitems_are_numbered(numbered_document):
    assert "(1)甲" in numbered_document
    assert "(2)乙" in numbered_document


def test_choice_groups_restart_at_a(numbered_document):
    """每道题都要从 A 开始，计数器必须在进入选项组时重置。"""

    assert "A.甲B.乙C.丙D.丁A.戊B.己C.庚D.辛" in numbered_document


def test_circled_items_are_generated(numbered_document):
    r"""圈码由列表标签生成，页面源码不手打 ①。

    ``\textcircled`` 的渲染结果是数字加 U+20DD COMBINING ENCLOSING CIRCLE，
    而不是预组合的 ①；两条路径都算"由类文件生成"，关键是源码里没有圈码字符。
    """

    assert "1\u20dd\u7532" in numbered_document
    assert "2\u20dd\u4e59" in numbered_document


def test_choice_layout_variants_exist(numbered_document):
    assert "(A)甲(B)乙(C)丙(D)丁" in numbered_document
    assert "A.甲B.乙" in numbered_document
    assert "C.丙D.丁" in numbered_document
