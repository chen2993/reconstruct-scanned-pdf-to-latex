"""手打编号审计：小问、选项、题号、圈码。

"编号由计数器产生"只靠人眼扫源码在几百页规模上必然漏，所以把它变成机械检查。

判据是**连续递进**而不是"出现过"：``由（1）式得`` 是引用，``（1）求定义域`` 才是
列表项；真实项目里单点命中会淹没在正文引用与坐标数据里。因此本审计只报成组的
``（1）→（2）``、``A. → B.``、``① → ②``，外加上行首题号/步骤号这类单点形态。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import BS, SCRIPTS

AUDIT = SCRIPTS / "audit_hardcoded_numbers.py"

BAD_PAGE = f"""% Source page: pages-001
{BS}begin{{bookbody}}
{BS}begin{{bookexample}}
求下列各题。
(1) 求 $f(x)$ 的定义域；
（2）判断连续性。
（1）写出反函数；
（2）讨论单调性。
A. $0$
（B）$+{BS}infty$
例 1.2 设函数 $f$ 连续。
步骤 1 先求导。
① 当 $x{BS}to0$ 时；
② 当 $x{BS}to{BS}infty$ 时。
{BS}end{{bookexample}}
{BS}end{{bookbody}}
"""

GOOD_PAGE = f"""% Source page: pages-002
{BS}begin{{bookbody}}
{BS}begin{{bookexample}}
求下列各题。
{BS}begin{{booksubitems}}
  {BS}item 求 $f(x)$ 的定义域；
  {BS}item 判断连续性。
{BS}end{{booksubitems}}
{BS}bookchoicesfour{{$0$}}{{$+{BS}infty$}}{{$-{BS}infty$}}{{不存在}}
{BS}end{{bookexample}}
{BS}end{{bookbody}}
"""

# 这些形态看起来像编号，其实全是引用、坐标或普通正文，必须放行。
REFERENCE_PAGE = f"""% Source page: pages-003
{BS}begin{{bookbody}}
{BS}begin{{booktext}}
由（1）式得 $x=1$。
①+③②式得 $y=2$。
多项式 $p(x)=x^2$ 在点 $(38.20,182.0)$ 取极值。
矩阵 $A$ 的 ${{BS}}operatorname{{rank}}(A)=2$。
方法 1 直接观察。
例 14 结论的本质仍是泰勒公式。
{BS}end{{booktext}}
{BS}begin{{tikzpicture}}
{BS}draw (v) -- (w);
{BS}coordinate (x) at (0,0);
{BS}end{{tikzpicture}}
{BS}end{{bookbody}}
"""


def make_project(root: Path, pages: dict[str, str]) -> Path:
    (root / "latex" / "pages").mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        (root / "latex" / "pages" / name).write_text(text, encoding="utf-8")
    return root


def audit(project: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(AUDIT), str(project), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_semantic_marks_pass(tmp_path):
    project = make_project(tmp_path / "good", {"pages-002.tex": GOOD_PAGE})
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "审计通过" in result.stdout


def test_references_and_coordinates_are_not_reported(tmp_path):
    """单个 (1) 与坐标 (38.20,182.0) 都不是列表项。"""

    project = make_project(tmp_path / "refs", {"pages-003.tex": REFERENCE_PAGE})
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "审计通过" in result.stdout


def test_every_literal_number_kind_is_caught(tmp_path):
    project = make_project(tmp_path / "bad", {"pages-001.tex": BAD_PAGE})
    result = audit(project)
    assert result.returncode == 1, result.stdout + result.stderr
    for code in (
        "hardcoded_subitem",
        "hardcoded_choice",
        "hardcoded_item_number",
        "hardcoded_step",
        "hardcoded_circled",
    ):
        assert code in result.stdout, code


def test_single_occurrence_is_not_enough(tmp_path):
    """单独一个 (1) 无法与「由（1）式得」区分，按设计不报。"""

    page = f"""% Source page: pages-020
{BS}begin{{bookbody}}
{BS}begin{{booktext}}
（1）求函数的定义域；
{BS}end{{booktext}}
{BS}end{{bookbody}}
"""
    project = make_project(tmp_path / "single", {"pages-020.tex": page})
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_numeric_choice_options_are_caught(tmp_path):
    """选项内容是纯数字时同样是手打选项标签。"""

    page = f"""% Source page: pages-021
{BS}begin{{bookbody}}
{BS}begin{{bookexample}}
下列正确的是（  ）。
A. 1
B. 2
C. 3
D. 4
{BS}end{{bookexample}}
{BS}end{{bookbody}}
"""
    project = make_project(tmp_path / "numbers", {"pages-021.tex": page})
    result = audit(project)
    assert result.returncode == 1
    assert "hardcoded_choice" in result.stdout


def test_tikz_node_names_are_not_choices(tmp_path):
    """(A) at (0,0) 是 TikZ 坐标名，不是选项。"""

    page = f"""% Source page: pages-022
{BS}begin{{bookbody}}
{BS}begin{{tikzpicture}}
{BS}coordinate (A) at (0,0);
{BS}coordinate (B) at (1,0);
{BS}draw (A) -- (B);
{BS}end{{tikzpicture}}
{BS}end{{bookbody}}
"""
    project = make_project(tmp_path / "tikz", {"pages-022.tex": page})
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_verbatim_content_is_ignored(tmp_path):
    """代码块里的 A. 与 (1)(2) 是代码，不是选项编号。"""

    page = f"""% Source page: pages-010
{BS}begin{{bookbody}}
{BS}begin{{lstlisting}}
A. this is code, not a choice
(1) still code
(2) still code
{BS}end{{lstlisting}}
{BS}end{{bookbody}}
"""
    project = make_project(tmp_path / "code", {"pages-010.tex": page})
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_comment_content_is_ignored(tmp_path):
    page = f"""% Source page: pages-011
% 备注：(1) 这行是注释，(2) 也不算编号
{BS}begin{{bookbody}}
{BS}begin{{booktext}}
正文。
{BS}end{{booktext}}
{BS}end{{bookbody}}
"""
    project = make_project(tmp_path / "comment", {"pages-011.tex": page})
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_allow_marker_exempts_a_group(tmp_path):
    """原书正文确实成组出现字面编号时，逐行加豁免标记。"""

    page = f"""% Source page: pages-012
{BS}begin{{bookbody}}
{BS}begin{{booktext}}
原书直接列举：（1）甲；% allow-number
（2）乙。% allow-number
{BS}end{{booktext}}
{BS}end{{bookbody}}
"""
    project = make_project(tmp_path / "allowed", {"pages-012.tex": page})
    result = audit(project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_json_report_shape(tmp_path):
    project = make_project(tmp_path / "bad2", {"pages-001.tex": BAD_PAGE})
    result = audit(project, "--json")
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["files_scanned"] == 1
    codes = {item["code"] for item in payload["issues"]}
    assert "hardcoded_subitem" in codes
    assert "hardcoded_choice" in codes
    assert all(
        "path" in item and "line" in item and "end_line" in item and "count" in item
        for item in payload["issues"]
    )


def test_missing_project_is_usage_error(tmp_path):
    result = audit(tmp_path / "absent")
    assert result.returncode == 2
    assert "项目目录不存在" in result.stderr
