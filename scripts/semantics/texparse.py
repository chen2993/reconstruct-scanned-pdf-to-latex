"""逐页 TeX 源码的低层扫描工具。"""

from __future__ import annotations

import bisect

from .models import Issue


def strip_comments(text: str) -> str:
    output = list(text)
    line_start = 0
    while line_start < len(text):
        newline = text.find("\n", line_start)
        line_end = len(text) if newline < 0 else newline
        index = line_start
        while index < line_end:
            if text[index] == "%":
                backslashes = 0
                cursor = index - 1
                while cursor >= line_start and text[cursor] == "\\":
                    backslashes += 1
                    cursor -= 1
                if backslashes % 2 == 0:
                    output[index:line_end] = " " * (line_end - index)
                    break
            index += 1
        if newline < 0:
            break
        line_start = newline + 1
    return "".join(output)


def skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def parse_group(text: str, index: int, opening: str, closing: str) -> tuple[str, int] | None:
    index = skip_space(text, index)
    if index >= len(text) or text[index] != opening:
        return None
    depth = 1
    cursor = index + 1
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text[cursor] == opening:
            depth += 1
        elif text[cursor] == closing:
            depth -= 1
            if depth == 0:
                return text[index + 1 : cursor], cursor + 1
        cursor += 1
    return None


def read_command(text: str, index: int) -> tuple[str, int]:
    cursor = index + 1
    if cursor >= len(text):
        return "", cursor
    if text[cursor].isalpha() or text[cursor] == "@":
        start = cursor
        while cursor < len(text) and (text[cursor].isalpha() or text[cursor] == "@"):
            cursor += 1
        return text[start:cursor], cursor
    return text[cursor], cursor + 1


def consume_command_arguments(text: str, index: int, required: int = 0) -> tuple[int, bool]:
    cursor = skip_space(text, index)
    optional = parse_group(text, cursor, "[", "]")
    if optional is not None:
        _, cursor = optional
    complete = True
    for _ in range(required):
        group = parse_group(text, cursor, "{", "}")
        if group is None:
            complete = False
            break
        _, cursor = group
    return cursor, complete


def line_column(newlines: list[int], index: int) -> tuple[int, int]:
    line_index = bisect.bisect_right(newlines, index)
    previous = -1 if line_index == 0 else newlines[line_index - 1]
    return line_index + 1, index - previous


def add_issue(
    issues: list[Issue], relative: str, newlines: list[int], index: int, code: str, message: str
) -> None:
    line, column = line_column(newlines, index)
    issues.append(Issue(relative, line, column, code, message))
