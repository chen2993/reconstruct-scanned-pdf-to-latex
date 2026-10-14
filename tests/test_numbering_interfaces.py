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


def assert_latex_success(result: subprocess.CompletedProcess, log: Path) -> None:
    """Treat a produced PDF/log as insufficient evidence of a valid compile."""

    assert result.returncode == 0, (result.stdout + result.stderr)[-5000:]
    assert log.is_file(), (result.stdout + result.stderr)[-5000:]
    text = log.read_text(encoding="utf-8", errors="replace")
    assert "LaTeX Error:" not in text
    assert "Package base Error:" not in text
    assert "Undefined control sequence" not in text


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
        + BS + "bookchoices[trace=true]{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoices{戊}{己}{庚}{辛}\n"
        + BS + "bookchoices[label=paren,mode=four]{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoices[mode=two]{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoices[mode=vertical]{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoices[mode=display,content=math]{\\frac{1}{2}}{x^2}{y^2}{z^2}\n"
        + BS + "bookchoices[label=cnparen,mode=four]{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoices[mode=figure,figure={\\rule{8mm}{8mm}}]{甲}{乙}{丙}{丁}\n"
        + BS + "bookchoices[mode=graphics]{\\rule{8mm}{8mm}}{\\rule{8mm}{8mm}}{\\rule{8mm}{8mm}}{\\rule{8mm}{8mm}}\n"
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
    assert_latex_success(result, work / "out" / "numbered.log")
    assert pdf.is_file(), result.stdout[-3000:]

    import fitz

    handle = fitz.open(pdf)
    text = "".join(page.get_text() for page in handle)
    handle.close()
    return re.sub(r"\s+", "", text)


@pytest.fixture(scope="module")
def numbering_log(tmp_path_factory, latex_env):
    """Compile a traced auto layout and return the compiler log."""

    work = tmp_path_factory.mktemp("choice-trace")
    class_source = (REPO / "template" / "base.cls").read_text(encoding="utf-8")
    class_source = class_source.replace(
        BS + "ProvidesClass{base}", BS + "ProvidesClass{traceprobe}"
    )
    class_source += "\n" + BS + "booksetoriginalpagesize{185mm}{260mm}\n"
    write(work / "traceprobe.cls", class_source)
    write(
        work / "main.tex",
        BS + "documentclass{traceprobe}\n"
        + BS + "begin{document}\n"
        + BS + "bookchoices[trace=true]{甲}{乙}{丙}{丁}\n"
        + BS + "end{document}\n",
    )
    result = subprocess.run(
        [
            "latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
            "-file-line-error", "-no-shell-escape", "-outdir=out", "-jobname=trace",
            "main.tex",
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=work, env=latex_env,
    )
    log = work / "out" / "trace.log"
    assert_latex_success(result, log)
    return log.read_text(encoding="utf-8", errors="replace")


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
    assert "（A）甲（B）乙（C）丙（D）丁" in numbered_document


def test_traced_auto_layout_reports_final_mode(numbering_log):
    assert "BOOKCHOICES mode=four" in numbering_log
    assert "BOOKCHOICES widths four=" in numbering_log


@pytest.mark.parametrize(
    ("choice_source", "error_text"),
    (
        (
            BS + "bookchoices[mode=display]{甲}{乙}{丙}{丁}\n",
            "Choice display mode requires content=math",
        ),
        (
            BS + "bookchoices[mode=graphics,content=math]{甲}{乙}{丙}{丁}\n",
            "Choice graphics mode requires content=graphic",
        ),
        (
            BS + "bookchoices[mode=figure,figure-gap=-1em,figure={\\rule{8mm}{8mm}}]{甲}{乙}{丙}{丁}\n",
            "Choice figure-gap cannot be negative",
        ),
        (
            BS + "bookchoices{\\textbf{甲}}{乙}{丙}{丁}\n",
            "Choice auto mode only accepts literal",
        ),
        (
            BS + "newcommand{\\emptychoice}{}\n"
            + BS + "bookchoices[mode=four]{甲}{\\emptychoice}{丙}{丁}\n",
            "Choice option B expands to empty",
        ),
    ),
)
def test_invalid_choice_configuration_fails_without_rendering(
    tmp_path, latex_env, choice_source, error_text
):
    """Invalid semantic combinations must fail loudly, not silently emit a choice."""

    work = tmp_path / "invalid-choice"
    class_source = (REPO / "template" / "base.cls").read_text(encoding="utf-8")
    class_source = class_source.replace(
        BS + "ProvidesClass{base}", BS + "ProvidesClass{invalidprobe}"
    )
    # 纸张尺寸是必需的导言区配置：不设置的话类文件会在 \begin{document} 就报错，
    # 那时还没轮到选择题参数校验，测试会误判成"错误信息没出现"。
    class_source += "\n" + BS + "booksetoriginalpagesize{185mm}{260mm}\n"
    write(work / "invalidprobe.cls", class_source)
    write(
        work / "main.tex",
        BS + "documentclass{invalidprobe}\n"
        + BS + "begin{document}\n"
        + choice_source
        + BS + "end{document}\n",
    )
    result = subprocess.run(
        [
            "latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
            "-file-line-error", "-no-shell-escape", "-outdir=out", "-jobname=invalid",
            "main.tex",
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=work, env=latex_env,
    )
    log = work / "out" / "invalid.log"
    assert result.returncode != 0
    assert log.is_file()
    assert not (work / "out" / "invalid.pdf").exists()
    text = re.sub(r"\s+", "", log.read_text(encoding="utf-8", errors="replace"))
    assert re.sub(r"\s+", "", error_text) in text
