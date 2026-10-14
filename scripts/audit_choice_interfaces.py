#!/usr/bin/env python3
"""审计正文页是否绕过统一的选择题入口。

正文页只允许使用项目类文件提供的 ``\\bookchoices``。审计器故意只做
接口级检查：不解析题目内容，也不把普通正文里的括号文字当成选择题。
注释、跨行调用和共享图形参数需要先被正确处理，否则最容易漏掉真实的
手工标签或把图形源码误报成页面选择题。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from semantics.texparse import parse_group, read_command, skip_space
except ImportError:  # pragma: no cover - supports importing from the repository root.
    from scripts.semantics.texparse import parse_group, read_command, skip_space


FORBIDDEN = (
    (re.compile(r"\\(?:choice|choicecell)\b"), "legacy_choice_command"),
    (
        re.compile(r"\\(?:begin|end)\s*\{choices\}"),
        "legacy_choices_environment",
    ),
    (
        re.compile(r"\\(?:begin|end)\s*\{choicecols\}"),
        "legacy_choicecols_environment",
    ),
    (
        re.compile(
            r"\\(?:"
            r"bookchoices(?:four|paren|twobytwo|vertical|display|figure|graphics)"
            r"|EDChoices[A-Za-z]*"
            r"|NPEEChoices[A-Za-z]*"
            r"|ExamChoices[A-Za-z]*"
            r"|(?:ED|NPEE|Exam)GraphicChoices"
            r"|(?:ED|NPEE|Exam)ChoiceGraphic"
            r")\*?\b"
        ),
        "legacy_choice_layout_command",
    ),
    (
        re.compile(
            r"\\item\s*\[\s*(?:"
            r"[A-H]\s*(?:[.)])?"
            r"|[\(（]\s*[A-H]\s*[\)）]"
            r")\s*\]"
        ),
        "manual_choice_label",
    ),
)

VERBATIM_ENVIRONMENTS = frozenset(
    {"comment", "lstlisting", "minted", "Verbatim", "verbatim", "verbatim*"}
)
INLINE_VERBATIM_COMMANDS = frozenset({"lstinline", "mintinline", "verb"})
STYLE_KEYS = frozenset(
    {"column-sep", "figure-gap", "graphic-max-height", "inset", "label-width", "row-sep"}
)
VERBATIM_END = re.compile(r"\\end\s*\{\s*([^{}]+?)\s*\}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="审计正文页的选择题接口。")
    parser.add_argument("project", type=Path, help="重建项目根目录")
    return parser.parse_args()


def page_files(project: Path) -> list[Path]:
    return sorted((project / "latex" / "pages").glob("pages-*.tex"))


def _blank_non_newlines(chars: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        if chars[index] not in "\r\n":
            chars[index] = " "


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return bool(backslashes % 2)


def _inline_verbatim_end(text: str, command_end: int, command: str) -> int:
    cursor = command_end
    if command == "verb" and cursor < len(text) and text[cursor] == "*":
        cursor += 1
    if command == "lstinline":
        optional = parse_group(text, skip_space(text, cursor), "[", "]")
        if optional is not None:
            _, cursor = optional
    if command == "mintinline":
        optional = parse_group(text, skip_space(text, cursor), "[", "]")
        if optional is not None:
            _, cursor = optional
        language = parse_group(text, skip_space(text, cursor), "{", "}")
        if language is not None:
            _, cursor = language
    if cursor >= len(text):
        return cursor
    delimiter = text[cursor]
    if delimiter in "\r\n":
        return cursor + 1
    closing = text.find(delimiter, cursor + 1)
    return len(text) if closing < 0 else closing + 1


def _mask_verbatim(text: str) -> str:
    """Blank comments and code/verbatim regions while preserving offsets."""

    masked = list(text)
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "%" and not is_escaped(text, cursor):
            line_end = text.find("\n", cursor)
            if line_end < 0:
                line_end = len(text)
            _blank_non_newlines(masked, cursor, line_end)
            cursor = line_end
            continue
        if text[cursor] != "\\":
            cursor += 1
            continue
        command, command_end = read_command(text, cursor)
        if command in INLINE_VERBATIM_COMMANDS:
            end = _inline_verbatim_end(text, command_end, command)
            _blank_non_newlines(masked, cursor, end)
            cursor = end
            continue
        if command != "begin":
            cursor = command_end
            continue
        environment_cursor = skip_space(text, command_end)
        optional = parse_group(text, environment_cursor, "[", "]")
        if optional is not None:
            _, environment_cursor = optional
        environment = parse_group(text, environment_cursor, "{", "}")
        if environment is None or environment[0].strip() not in VERBATIM_ENVIRONMENTS:
            cursor = command_end
            continue
        environment_name, body_start = environment
        closing = None
        for match in VERBATIM_END.finditer(text, body_start):
            if match.group(1).strip() == environment_name.strip():
                closing = match.end()
                break
        end = len(text) if closing is None else closing
        _blank_non_newlines(masked, cursor, end)
        cursor = end
    return "".join(masked)


def strip_comments_preserving_offsets(text: str) -> str:
    """Keep the old helper name while masking comments and verbatim regions."""

    return _mask_verbatim(text)


def balanced_end(text: str, start: int, opening: str, closing: str) -> int | None:
    """Return the exclusive end of a balanced TeX delimiter pair."""

    if start >= len(text) or text[start] != opening:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char != opening and char != closing:
            continue
        if is_escaped(text, index):
            continue
        if char == opening:
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def choice_figure_spans(text: str) -> list[tuple[int, int]]:
    """Find ``figure={...}`` values inside ``\\bookchoices[...]`` options.

    A figure body may contain arbitrary TeX, including an illustrative
    ``\\item[A.]`` string. That string is not a page choice and must not trip
    the manual-label rule.
    """

    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\\bookchoices\s*\[", text):
        bracket_start = text.find("[", match.start(), match.end())
        bracket_end = balanced_end(text, bracket_start, "[", "]")
        if bracket_end is None:
            continue
        options = text[bracket_start:bracket_end]
        figure_match = re.search(r"\bfigure\s*=\s*", options)
        if figure_match is None:
            continue
        value_start = bracket_start + figure_match.end()
        while value_start < bracket_end and text[value_start].isspace():
            value_start += 1
        if value_start >= bracket_end or text[value_start] != "{":
            continue
        value_end = balanced_end(text, value_start, "{", "}")
        if value_end is not None and value_end <= bracket_end:
            spans.append((value_start, value_end))
    return spans


def _top_level_key(text: str, start: int, end: int) -> tuple[str, int] | None:
    stack: list[str] = []
    cursor = start
    equals = None
    while cursor < end:
        char = text[cursor]
        if char == "\\":
            _, cursor = read_command(text, cursor)
            continue
        if char in "[{":
            stack.append(char)
        elif stack and ((stack[-1] == "[" and char == "]") or (stack[-1] == "{" and char == "}")):
            stack.pop()
        elif char == "=" and not stack:
            equals = cursor
            break
        cursor += 1
    if equals is None:
        return None
    raw = text[start:equals]
    leading = len(raw) - len(raw.lstrip())
    key = raw.strip()
    if not key:
        return None
    return key, start + leading


def _top_level_keys(text: str, start: int, end: int):
    segment_start = start
    stack: list[str] = []
    cursor = start
    while cursor < end:
        char = text[cursor]
        if char == "\\":
            _, cursor = read_command(text, cursor)
            continue
        if char in "[{":
            stack.append(char)
        elif stack and ((stack[-1] == "[" and char == "]") or (stack[-1] == "{" and char == "}")):
            stack.pop()
        elif char == "," and not stack:
            item = _top_level_key(text, segment_start, cursor)
            if item is not None:
                yield item
            segment_start = cursor + 1
        cursor += 1
    item = _top_level_key(text, segment_start, end)
    if item is not None:
        yield item


def in_spans(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def line_snippet(lines: list[str], start_line: int, end_line: int) -> str:
    selected = lines[max(start_line - 1, 0) : min(end_line, len(lines))]
    return " ".join(line.strip() for line in selected).strip()


def add_issue(
    issues: list[dict[str, object]],
    path: Path,
    original: str,
    lines: list[str],
    start: int,
    end: int,
    code: str,
    match: str,
) -> None:
    line_number = original.count("\n", 0, start) + 1
    end_line = original.count("\n", 0, end) + 1
    issues.append(
        {
            "file": str(path),
            "line": line_number,
            "end_line": end_line,
            "code": code,
            "detail": line_snippet(lines, line_number, end_line),
            "match": " ".join(match.split()),
        }
    )


def audit(project: Path) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for path in page_files(project):
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(
                {"file": str(path), "line": 0, "code": "read_error", "detail": str(exc)}
            )
            continue

        text = strip_comments_preserving_offsets(original)
        lines = original.splitlines()
        figure_spans = choice_figure_spans(text)
        for pattern, code in FORBIDDEN:
            for match in pattern.finditer(text):
                if code == "manual_choice_label" and in_spans(match.start(), figure_spans):
                    continue
                add_issue(
                    issues,
                    path,
                    original,
                    lines,
                    match.start(),
                    match.end(),
                    code,
                    match.group(0),
                )

        cursor = 0
        while cursor < len(text):
            if text[cursor] != "\\":
                cursor += 1
                continue
            command, command_end = read_command(text, cursor)
            if command != "bookchoices":
                cursor = command_end
                continue
            option_start = skip_space(text, command_end)
            option_group = parse_group(text, option_start, "[", "]")
            if option_group is None:
                cursor = command_end
                continue
            _, option_end = option_group
            for key, key_index in _top_level_keys(text, option_start + 1, option_end - 1):
                if key in STYLE_KEYS:
                    add_issue(
                        issues,
                        path,
                        original,
                        lines,
                        # 只报键名所在行：多行选项块里，直接指到 ``column-sep`` /
                        # ``trace`` 那一行才改得动；报整段会让人还得自己找。
                        key_index,
                        key_index + len(key),
                        "page_choice_style_override",
                        key,
                    )
                elif key == "trace":
                    value_start = skip_space(text, key_index + len(key))
                    if value_start < option_end and text[value_start] == "=":
                        value_start = skip_space(text, value_start + 1)
                        value_end = value_start
                        while value_end < option_end - 1 and text[value_end] not in ",\n":
                            value_end += 1
                        if text[value_start:value_end].strip() == "true":
                            add_issue(
                                issues,
                                path,
                                original,
                                lines,
                                key_index,
                                key_index + len(key),
                                "choice_trace_in_final",
                                key,
                            )
            cursor = command_end
    return sorted(
        issues,
        key=lambda issue: (str(issue["file"]), int(issue["line"]), str(issue["code"])),
    )


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        print(f"项目目录不存在: {project}", file=sys.stderr)
        return 2
    issues = audit(project)
    if issues:
        print(f"选择题接口审计失败：发现 {len(issues)} 处绕过统一入口的问题。")
        for issue in issues:
            location = f"{issue['file']}:{issue['line']}"
            if issue.get("end_line", issue["line"]) != issue["line"]:
                location += f"-{issue['end_line']}"
            print(f"- {location} [{issue['code']}] {issue['detail']}")
        print("正文页只允许使用 \\bookchoices；请不要把参考项目旧接口带入当前项目。")
        return 1
    print("选择题接口审计通过：正文页未发现旧式选择题接口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
