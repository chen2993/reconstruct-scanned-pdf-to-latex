"""审计正文的来源页标记：每页恰好一个、与文件名一致、且严格递增。

两个项目都需要回答"这段内容来自原书哪一页"。来源页标记必须可机器校验，
否则重编号、合并、迁移之后很容易出现漏页、重复或错位，而人工复核只抽样
发现不了。本脚本只读源码文本，不读取 PDF 或页图。

支持两种等价写法（由项目 `.cls` 约定后固定使用一种）：

* 注释形式（默认约定）：``% Source page: pages-023``
* 空指令形式：``\\booksourcepage{pages-023}%``（需在 ``standalone_commands``
  中登记，否则语义审计会把它当成顶层命令）
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

COMMENT_MARKER = re.compile(r"^\s*%\s*Source page:\s*(\S+)\s*$")
PAGE_FILE = re.compile(r"^pages-(\d+)\.tex$")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    message: str


class ConfigurationError(RuntimeError):
    """项目结构或输入不可用；与内容问题区分，退出码为 2。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="审计 latex/pages 的正文来源页标记；不读取 PDF 或页图。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument(
        "--command",
        default="booksourcepage",
        help="空指令形式的标记命令名（默认 booksourcepage）",
    )
    return parser.parse_args()


def markers_in(text: str, command: str) -> list[tuple[int, str]]:
    """Return (line, identifier) for every provenance marker in one file."""
    command_pattern = re.compile(
        r"\\" + re.escape(command) + r"\s*\{\s*([^{}\s]+)\s*\}"
    )
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        comment = COMMENT_MARKER.match(line)
        if comment is not None:
            found.append((number, comment.group(1)))
        for match in command_pattern.finditer(line):
            found.append((number, match.group(1)))
    return found


def audit(project: Path, command: str) -> list[Finding]:
    body = project / "latex" / "pages"
    if not body.is_dir():
        raise ConfigurationError(f"缺少正文目录: {body}")

    findings: list[Finding] = []
    files = sorted(
        (path for path in body.glob("pages-*.tex") if path.is_file()),
        key=lambda path: int(PAGE_FILE.match(path.name).group(1))
        if PAGE_FILE.match(path.name)
        else 1 << 30,
    )
    if not files:
        raise ConfigurationError(f"正文目录中没有 pages-*.tex: {body}")

    seen: dict[str, str] = {}
    previous_number: int | None = None
    for path in files:
        relative = path.relative_to(project).as_posix()
        match = PAGE_FILE.match(path.name)
        if match is None:
            findings.append(
                Finding(relative, 0, "bad_page_filename", f"正文文件名不规范: {path.name}")
            )
            continue
        number = int(match.group(1))
        expected = f"pages-{number:03d}"

        text = path.read_text(encoding="utf-8")
        markers = markers_in(text, command)
        if not markers:
            findings.append(
                Finding(
                    relative,
                    0,
                    "missing_source_marker",
                    f"缺少来源页标记；应写 `% Source page: {expected}`",
                )
            )
        elif len(markers) > 1:
            lines = ", ".join(str(line) for line, _ in markers)
            findings.append(
                Finding(
                    relative,
                    markers[0][0],
                    "duplicate_source_marker",
                    f"一页出现 {len(markers)} 个来源页标记（行 {lines}）",
                )
            )
        for line, identifier in markers:
            if identifier != expected:
                findings.append(
                    Finding(
                        relative,
                        line,
                        "source_marker_mismatch",
                        f"来源页标记 {identifier!r} 与文件名不符，应为 {expected!r}",
                    )
                )
            owner = seen.get(identifier)
            if owner is not None:
                findings.append(
                    Finding(
                        relative,
                        line,
                        "source_marker_reused",
                        f"来源页标记 {identifier!r} 已在 {owner} 使用",
                    )
                )
            else:
                seen[identifier] = relative

        if previous_number is not None and number <= previous_number:
            findings.append(
                Finding(
                    relative,
                    0,
                    "source_page_out_of_order",
                    f"正文页顺序不递增: {number} 出现在 {previous_number} 之后",
                )
            )
        previous_number = number

    return findings


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    try:
        findings = audit(project, args.command)
    except ConfigurationError as exc:
        print(f"来源页标记审计配置错误: {exc}", file=sys.stderr)
        return 2
    if not findings:
        print("来源页标记审计通过。")
        return 0
    for finding in findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        print(f"{location}: {finding.code}: {finding.message}")
    print(f"来源页标记审计未通过：{len(findings)} 个问题")
    return 1


if __name__ == "__main__":
    sys.exit(main())
