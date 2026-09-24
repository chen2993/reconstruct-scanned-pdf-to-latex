#!/usr/bin/env python3
"""审计逐页源码里的手打编号：小问、选项、题号、圈码、步骤号。

为什么需要脚本
--------------
"编号必须由计数器产生"这条规则只靠人眼扫源码，在几百页规模上必然漏。最常见的
违规是把小问写成 ``(1) 求……``、把选项写成 ``A. ……``：它们看起来"完全正常"、
编译也不报错，但会导致编号样式与原书不一致、跨页续写重号、且无法交叉引用与筛选。

判据：连续递进，而不是"出现过"
--------------------------------
单个 ``（1）`` 无法区分列表项和公式引用：``由（1）式得`` 是引用，``（1）求定义域``
是列表。若按"行首出现就报"实现，真实项目会命中上千处正文引用、坐标数据与函数
参数，噪声大到 agent 会直接忽略审计。可靠的结构判据是**连续递进**：
``（1）→（2）`` 或 ``A. → B.`` 这种成组出现，才只可能是编者手打的编号。

本脚本报两类：

1. 同一族标签在同一个页面源码文件里连续递进至少两项；单行内
   ``（1）……；（2）……`` 也算；
2. 少数"出现即违规"的单点形态：行首重复手打的 ``例 10``、``步骤 1``。

会被排除的形态：``由（1）式得``、``①+③②式得``、``(38.20,182.0)``、
``\\draw (v) -- (w)``（TikZ 坐标名）、``rank(A)``、``方法 1``、``例 14 结论``。

误报处理：确实需要字面编号的行，在**同一行**加 ``allow-number`` 注释豁免。

用法::

    python -X utf8 scripts/audit_hardcoded_numbers.py <project>
    python -X utf8 scripts/audit_hardcoded_numbers.py <project> --json
    python -X utf8 scripts/audit_hardcoded_numbers.py <project> --max-print 20
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BS = chr(92)

# 只扫逐页与前后置源码的顶层文件；图形模块（figures/）是坐标与图内标注，整体不扫。
SCAN_DIRS = ("latex/pages", "latex/front", "latex/back")

ALLOW_MARKER = "allow-number"

# 同一文件内连续两项之间最多隔多少行；太松会把不同题目的编号接成一条链。
MAX_RUN_GAP = 30

# 行首可选的 LaTeX 结构前缀，排除正文中间的引用与函数参数。
PREFIX = (
    r"^\s*(?:"
    + BS + BS + r"(?:begin|end)\{[^}]*\}"
    + r"|" + BS + BS + r"(?:item|par)\b"
    + r")?\s*"
)

# 标签后紧跟这些字符的，是引用而不是列表项：（1）式、（1）、（2）、（1）和（2）。
REFERENCE_FOLLOW = ("式", "、", "，", ",", "和", "与", "或", "及", "中", "得", "+", "-", "×", "÷", "=")

# ``例 14 结论`` 这类是引用，不是重复手打的题号。
REFERENCE_WORDS = (
    "结论", "已", "中", "的", "所", "给出", "说明", "指出", "表明", "提示",
    "告诉我们", "是", "解法", "方法", "本质",
)

# 行内第二个及以后的标签，必须跟在这些分隔符之后才可信。
INLINE_SEPARATOR = "；;。.!！?？，,"

CIRCLED_CHARS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

ARABIC = re.compile(r"^[（(](\d{1,2})[）)]")
ROMAN = re.compile(r"^[（(]([ivxIVX]{1,5})[）)]")
CHOICE_PAREN = re.compile(r"^[（(]([A-H])[）)]")
CHOICE_DOT = re.compile(r"^([A-H])[.．、]")
ITEM_NUMBER = re.compile(
    PREFIX + r"(?:例|例题|习题|练习题|定理|定义|引理|推论|性质)\s*(\d{1,3})"
)
STEP_NUMBER = re.compile(PREFIX + r"(?:步骤|Step)\s*(\d{1,2})")

INLINE_ARABIC = re.compile(r"(?<=[" + INLINE_SEPARATOR + r"])\s*[（(](\d{1,2})[）)]")
INLINE_CHOICE = re.compile(
    r"(?<=[" + INLINE_SEPARATOR + r"])\s*(?:[（(]([A-H])[）)]|([A-H])[.．、])"
)
INLINE_CIRCLED = re.compile(r"(?<=[" + INLINE_SEPARATOR + r"])\s*([" + CIRCLED_CHARS + r"])")

# 代码块内容不算编号；用等量换行替换，保留行号。
VERBATIM = re.compile(
    BS + BS + r"begin\{(?:verbatim|lstlisting|minted)\*?\}.*?"
    + BS + BS + r"end\{(?:verbatim|lstlisting|minted)\*?\}",
    re.DOTALL,
)

# 图形代码里大量出现 (v)、(x) 这类坐标名，整行按代码处理。
CODE_COMMANDS = (
    BS + "draw", BS + "coordinate", BS + "node", BS + "path",
    BS + "fill", BS + "foreach", BS + "tkz", BS + "def",
)

ROMAN_VALUES = {"i": 1, "v": 5, "x": 10}
CJK = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")


def blank_verbatim(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return chr(10) * match.group(0).count(chr(10))

    return VERBATIM.sub(replace, text)


def comment_cut(line: str) -> int:
    """返回该行第一个未被转义的 ``%`` 的位置；没有注释则返回行尾。"""

    for index, char in enumerate(line):
        if char != "%":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == BS:
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return index
    return len(line)


def strip_comments(text: str) -> list[tuple[int, str]]:
    return [
        (number, line[: comment_cut(line)])
        for number, line in enumerate(text.splitlines(), start=1)
    ]


def roman_value(text: str) -> int:
    total = 0
    previous = 0
    for char in reversed(text.lower()):
        value = ROMAN_VALUES[char]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total


def looks_like_code(line: str) -> bool:
    stripped = line.lstrip()
    if "--" in stripped:
        return True
    return any(stripped.startswith(command) for command in CODE_COMMANDS)


def is_reference(after: str) -> bool:
    """标签后紧跟引用词或什么都没有，说明这不是列表项。"""

    stripped = after.lstrip()
    if not stripped:
        return True
    return stripped[0] in REFERENCE_FOLLOW


def content_follows(after: str) -> bool:
    """标签后必须紧跟内容，才算列表项；``(A) at (1,2)`` 是 TikZ 坐标，不是选项。"""

    stripped = after.lstrip()
    if not stripped:
        return False
    if stripped.startswith("at ") or stripped.startswith("at("):
        return False
    first = stripped[0]
    return first == "$" or bool(CJK.match(first)) or first.isalnum()


def is_reference_word(after: str) -> bool:
    stripped = after.lstrip()
    if not stripped:
        return False
    return any(stripped.startswith(word) for word in REFERENCE_WORDS)


def start_label(line: str) -> tuple[str, int, str] | None:
    """提取行首编号标签，返回 (标签族, 序号, 标签后的内容)。"""

    match = ITEM_NUMBER.match(line)
    if match:
        return "itemnum", int(match.group(1)), line[match.end() :]

    match = STEP_NUMBER.match(line)
    if match:
        return "step", int(match.group(1)), line[match.end() :]

    if looks_like_code(line):
        return None

    match = re.match(PREFIX, line)
    rest = line[match.end() :] if match else line
    if not rest:
        return None

    if rest[0] in CIRCLED_CHARS:
        after = rest[1:]
        if is_reference(after):
            return None
        return "circled", CIRCLED_CHARS.index(rest[0]) + 1, after

    match = ARABIC.match(rest)
    if match:
        after = rest[match.end() :]
        if is_reference(after):
            return None
        return "subitem", int(match.group(1)), after

    match = ROMAN.match(rest)
    if match:
        after = rest[match.end() :]
        value = roman_value(match.group(1))
        if 1 <= value <= 30 and content_follows(after):
            return "subitem_roman", value, after
        return None

    match = CHOICE_PAREN.match(rest)
    if match:
        after = rest[match.end() :]
        if content_follows(after):
            return "choice", ord(match.group(1).upper()) - ord("A") + 1, after
        return None

    match = CHOICE_DOT.match(rest)
    if match:
        after = rest[match.end() :]
        if content_follows(after):
            return "choice", ord(match.group(1).upper()) - ord("A") + 1, after
        return None

    return None


def inline_continuations(family: str, start_index: int, line: str) -> list[int]:
    """返回同一行里紧接着出现的后续编号。"""

    if family == "subitem":
        pattern = INLINE_ARABIC

        def to_index(match: re.Match[str]) -> int:
            return int(match.group(1))
    elif family == "choice":
        pattern = INLINE_CHOICE

        def to_index(match: re.Match[str]) -> int:
            letter = match.group(1) or match.group(2)
            return ord(letter.upper()) - ord("A") + 1
    elif family == "circled":
        pattern = INLINE_CIRCLED

        def to_index(match: re.Match[str]) -> int:
            return CIRCLED_CHARS.index(match.group(1)) + 1
    else:
        return []

    found: list[int] = []
    expected = start_index + 1
    for match in pattern.finditer(line):
        index = to_index(match)
        if index == expected:
            found.append(index)
            expected += 1
    return found


def code_for_family(family: str) -> str:
    if family == "choice":
        return "hardcoded_choice"
    if family == "circled":
        return "hardcoded_circled"
    if family == "itemnum":
        return "hardcoded_item_number"
    if family == "step":
        return "hardcoded_step"
    return "hardcoded_subitem"


SINGLE_FAMILIES = ("itemnum", "step")


def audit_file(path: Path, project: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    lines = strip_comments(blank_verbatim(chr(10).join(raw_lines)))
    relative = path.relative_to(project).as_posix()

    events: list[tuple[int, str, int, str]] = []
    for number, line in lines:
        raw = raw_lines[number - 1] if number - 1 < len(raw_lines) else ""
        if ALLOW_MARKER in raw:
            continue
        label = start_label(line)
        if label is None:
            continue
        family, index, _after = label
        if family in SINGLE_FAMILIES:
            after = _after
            if not (family == "itemnum" and is_reference_word(after)):
                findings.append(
                    {
                        "path": relative,
                        "line": number,
                        "end_line": number,
                        "count": 1,
                        "code": code_for_family(family),
                        "text": line.strip()[:120],
                    }
                )
            continue
        events.append((number, family, index, line))
        for extra in inline_continuations(family, index, line):
            events.append((number, family, extra, line))

    # 连续递进才报：单个 (1) 无法与「由（1）式得」区分开。
    run: list[tuple[int, str, int, str]] = []
    for event in events:
        number, family, index, line = event
        continues = bool(
            run
            and run[-1][1] == family
            and index == run[-1][2] + 1
            and number - run[-1][0] <= MAX_RUN_GAP
        )
        if not continues:
            if len(run) >= 2:
                findings.append(run_finding(relative, run))
            run = []
        run.append(event)
    if len(run) >= 2:
        findings.append(run_finding(relative, run))

    findings.sort(key=lambda item: (int(item["line"]), str(item["code"])))
    return findings


def run_finding(relative: str, run: list[tuple[int, str, int, str]]) -> dict[str, object]:
    first_line, family, _index, text = run[0]
    lines = [entry[0] for entry in run]
    return {
        "path": relative,
        "line": min(lines),
        "end_line": max(lines),
        "count": len(run),
        "code": code_for_family(family),
        "text": text.strip()[:120],
    }


def collect(project: Path) -> tuple[list[dict[str, object]], int]:
    findings: list[dict[str, object]] = []
    scanned = 0
    for directory in SCAN_DIRS:
        root = project / directory
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.tex")):
            scanned += 1
            findings.extend(audit_file(path, project))
    return findings, scanned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="审计逐页源码里的手打编号（小问、选项、题号、圈码、步骤号）。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument(
        "--max-print",
        type=int,
        default=40,
        help="终端最多打印多少条（默认 40）；完整清单用 --json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        print(f"项目目录不存在: {project}", file=sys.stderr)
        return 2

    findings, scanned = collect(project)

    if args.json:
        print(
            json.dumps(
                {"ok": not findings, "files_scanned": scanned, "issues": findings},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if findings else 0

    if not findings:
        print(f"手打编号审计通过：{scanned} 个文件中未发现成组字面编号。")
        return 0

    limit = max(args.max_print, 0)
    for item in findings[:limit]:
        span = (
            str(item["line"])
            if item["line"] == item["end_line"]
            else f"{item['line']}-{item['end_line']}"
        )
        print(
            f"{item['path']}:{span}: {item['code']}: "
            f"{item['count']} 项: {item['text']}"
        )
    if len(findings) > limit:
        print(f"... 其余 {len(findings) - limit} 条见 --json")

    counts: dict[str, int] = {}
    for item in findings:
        key = str(item["code"])
        counts[key] = counts.get(key, 0) + 1
    summary = "，".join(f"{key} {value} 组" for key, value in sorted(counts.items()))

    print(
        chr(10)
        + f"手打编号审计未通过：{len(findings)} 组（{summary}）。"
        + chr(10)
        + "这些编号必须由 .cls 的语义列表、选项命令或题目环境生成"
        + "（见 references/contract/page-authoring.md 第 1.5 节）。"
        + chr(10)
        + "若该处确实是原书正文里的字面编号，在同一行加 `"
        + ALLOW_MARKER
        + "` 豁免。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
