"""统一选择题入口的静态门禁。"""

from __future__ import annotations

import subprocess
import sys

from conftest import SCRIPTS


def run_audit(project):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "audit_choice_interfaces.py"), str(project)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_unified_choice_entry_passes(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    (pages / "pages-001.tex").write_text(
        r"\bookchoices{甲}{乙}{丙}{丁}" + "\n", encoding="utf-8"
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 0, result.stdout + result.stderr


def test_legacy_choice_interfaces_fail(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    (pages / "pages-001.tex").write_text(
        "\\begin{choices}\n"
        "  \\item[A.] 甲\n"
        "  \\item[A] 戊\n"
        "\\end{choices}\n"
        "\\choicecell{B}{乙}\n"
        "\\EDChoicesFour{甲}{乙}{丙}{丁}\n"
        "\\bookchoicesfour{甲}{乙}{丙}{丁}\n"
        "\\ExamGraphicChoices{甲}{乙}{丙}{丁}\n"
        "\\bookchoices[column-sep=0pt]{甲}{乙}{丙}{丁}\n"
        "\\bookchoices[trace=true]{甲}{乙}{丙}{丁}\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 1
    assert "legacy_choices_environment" in result.stdout
    assert "manual_choice_label" in result.stdout
    assert "legacy_choice_command" in result.stdout
    assert "legacy_choice_layout_command" in result.stdout
    assert "page_choice_style_override" in result.stdout
    assert "choice_trace_in_final" in result.stdout


def test_audit_handles_whitespace_multiline_labels_and_comments(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    (pages / "pages-002.tex").write_text(
        "% \\item[A.] 这是注释，不应触发\n"
        r"\begin{choices}" + "\n"
        r"  \item [ A. ] 甲" + "\n"
        r"  \item" + "\n"
        r"    [（B）] 乙" + "\n"
        r"\end{choices}" + "\n"
        r"\bookchoices[" + "\n"
        r"  column-sep=1em," + "\n"
        r"  trace=true" + "\n"
        r"]{甲}{乙}{丙}{丁}" + "\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 1
    assert "pages-002.tex:2" in result.stdout
    assert "manual_choice_label" in result.stdout
    # 审计按"键名所在行"报位置（与 test_nested_choice_keys... 的契约一致）：
    # column-sep 在第 8 行、trace 在第 9 行，都在多行选项块里。
    assert "pages-002.tex:8" in result.stdout
    assert "pages-002.tex:9" in result.stdout
    assert "page_choice_style_override" in result.stdout
    assert "choice_trace_in_final" in result.stdout
    assert "% \\item[A.]" not in result.stdout


def test_audit_does_not_treat_figure_body_as_page_choices(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    (pages / "pages-003.tex").write_text(
        r"\bookchoices[mode=figure,figure={\begin{array}{l}\item[A.]\end{array}}]"
        r"{甲}{乙}{丙}{丁}" + "\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 0, result.stdout + result.stderr


def test_audit_keeps_ordinary_custom_item_labels_out_of_choice_errors(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    (pages / "pages-004.tex").write_text(
        r"\begin{description}" + "\n"
        r"  \item[提示] 这不是选择题标签" + "\n"
        r"\end{description}" + "\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 0, result.stdout + result.stderr


def test_comments_and_verbatim_choice_like_text_are_ignored(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    (pages / "pages-005.tex").write_text(
        "% \\item[A.] and \\bookchoices[column-sep=0pt]{甲}{乙}{丙}{丁}\n"
        "\\verb|\\item[(B)] \\bookchoices[trace=true]{甲}{乙}{丙}{丁}|\n"
        "\\mintinline[python]{text}|\\item[（D）] \\bookchoices[trace=true]{甲}{乙}{丙}{丁}|\n"
        "\\begin{verbatim}\n"
        "\\item[（C）]\n"
        "\\bookchoices[column-sep=0pt]{甲}{乙}{丙}{丁}\n"
        "\\end{verbatim}\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 0, result.stdout + result.stderr


def test_code_after_verbatim_with_percent_is_still_audited(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    page = pages / "pages-006.tex"
    page.write_text(
        "\\verb|% \\item[A.]|\\bookchoices[column-sep=0pt]{甲}{乙}{丙}{丁}\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 1
    assert "[page_choice_style_override]" in result.stdout
    assert f"{page}:1 [page_choice_style_override]" in result.stdout
    assert "[manual_choice_label]" not in result.stdout


def test_nested_choice_keys_are_not_treated_as_page_style_overrides(tmp_path):
    pages = tmp_path / "project" / "latex" / "pages"
    pages.mkdir(parents=True)
    page = pages / "pages-007.tex"
    page.write_text(
        "\\bookchoices[\n"
        "  mode=four,\n"
        "  column-sep = 0pt,\n"
        "  figure={\\subfigure[column-sep=1pt]{row-sep=2pt}},\n"
        "  trace = true\n"
        "]\n"
        "  {甲}{乙}{丙}{丁}\n",
        encoding="utf-8",
    )
    result = run_audit(tmp_path / "project")
    assert result.returncode == 1
    assert result.stdout.count("[page_choice_style_override]") == 1
    assert result.stdout.count("[choice_trace_in_final]") == 1
    assert f"{page}:3 [page_choice_style_override]" in result.stdout
    assert f"{page}:5 [choice_trace_in_final]" in result.stdout
