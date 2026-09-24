#!/usr/bin/env python3
"""Audit the single automatic table-of-contents module without reading PDF text."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from page_workspace import resolve_entry  # noqa: E402


AUTO_COMMAND = re.compile(r"\\bookmaketoc(?![A-Za-z@])")
TOC_INPUT = re.compile(r"\\input\s*\{\s*front/toc(?:\.tex)?\s*\}")
FORBIDDEN_COMMANDS = re.compile(
    r"\\(?:addcontentsline|addtocontents|contentsline|@dottedtocline)(?![A-Za-z@])"
)


def strip_comments(source: str) -> str:
    """Remove TeX comments while preserving line boundaries for diagnostics."""

    lines: list[str] = []
    for line in source.splitlines(keepends=True):
        backslashes = 0
        cut = len(line)
        for index, char in enumerate(line):
            if char == "\\":
                backslashes += 1
                continue
            if char == "%" and backslashes % 2 == 0:
                cut = index
                break
            backslashes = 0
        lines.append(line[:cut])
    return "".join(lines)


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"无法读取 UTF-8 文件 {path}: {exc}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检查 toc.tex 是否恰好调用一次自动目录指令。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    toc_path = project / "latex" / "front" / "toc.tex"
    try:
        main_path = resolve_entry(project)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not toc_path.is_file() or not main_path.is_file():
        print("缺少 latex/front/toc.tex 或入口文件。", file=sys.stderr)
        return 2

    try:
        toc = strip_comments(read_utf8(toc_path))
        main = strip_comments(read_utf8(main_path))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    errors: list[str] = []
    auto_calls = AUTO_COMMAND.findall(toc)
    if len(auto_calls) != 1:
        errors.append(f"toc.tex 必须恰好调用一次 \\bookmaketoc，实际为 {len(auto_calls)} 次。")
    forbidden = FORBIDDEN_COMMANDS.findall(toc)
    if forbidden:
        errors.append(
            "toc.tex 禁止手写目录条目或页码命令: "
            + ", ".join(sorted(set(forbidden)))
        )
    toc_inputs = TOC_INPUT.findall(main)
    if len(toc_inputs) != 1:
        errors.append(f"{main_path.name} 必须恰好导入一次 front/toc，实际为 {len(toc_inputs)} 次。")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"自动目录审计通过：toc.tex 一次 bookmaketoc，{main_path.name} 一次 front/toc。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
