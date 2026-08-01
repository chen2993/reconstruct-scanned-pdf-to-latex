#!/usr/bin/env python3
"""审计逐页 TeX 的语义所有权与跨页环境结构。"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTROL_DIR = ".reconstruct-scanned-pdf-to-latex"
CONFIG_FILENAME = "semantic-audit.json"
ROOT_OWNER = "$root"
# Hyphens are valid in filenames, but not in LaTeX environment, command,
# counter, or configuration identifiers.  Reject them at the audit boundary.
ENVIRONMENT_NAME = re.compile(r"[A-Za-z@][A-Za-z0-9@*:_]*")
COMMAND_NAME = re.compile(r"[A-Za-z@][A-Za-z0-9@:_]*")

DEFAULT_OWNER_ENVIRONMENTS = frozenset(
    {
        "bookfrontmatterblock",
        "bookbackmatterblock",
        "booksupplement",
        "bookbody",
        "booktext",
        "bookexposition",
        "textbookexposition",
        "bookknowledgeprose",
        "knowledgeprose",
        "bookknowledgeblock",
        "bookknowledgeblockopen",
        "bookknowledgeblockmiddle",
        "bookknowledgeblockcontinued",
        "knowledgeblock",
        "knowledgeblockopen",
        "knowledgeblockmiddle",
        "knowledgeblockcontinued",
        "bookknowledgeopen",
        "bookknowledgemiddle",
        "bookknowledgecontinued",
        "bookdefinition",
        "booktheorem",
        "booklemma",
        "bookproposition",
        "bookcorollary",
        "bookproperty",
        "bookconcept",
        "bookproof",
        "bookexample",
        "bookexamplestart",
        "bookexamplecontinuation",
        "bookexampleend",
        "bookexercise",
        "bookexercisestart",
        "bookexercisecontinuation",
        "bookexerciseend",
        "bookquestion",
        "bookquestionstart",
        "bookquestioncontinuation",
        "bookquestionend",
        "bookanswer",
        "booksolution",
        "bookanalysis",
        "bookhint",
        "bookmethodstep",
        "bookproofstep",
        "bookanalysisstep",
        "booksolutionstep",
        "bookcase",
        "bookremark",
        "booknote",
        "booktip",
        "bookwarning",
        "booksummary",
        "bookfigure",
        "booktable",
        "bookalgorithm",
        "bookequation",
        "bookformula",
    }
)

DEFAULT_STRUCTURE_COMMANDS = frozenset(
    {
        "bookpart",
        "bookchapter",
        "booksection",
        "booksubsection",
        "booksubsubsection",
        "bookparagraph",
    }
)

# 这些是内部布局或媒体组件，不是语义所有者，必须继承外层所有者。
DEFAULT_MEDIA_ENVIRONMENTS = frozenset(
    {
        "figure",
        "figure*",
        "table",
        "table*",
        "tabular",
        "tabular*",
        "tabularx",
        "longtable",
        "tikzpicture",
        "axis",
        "algorithm",
        "algorithmic",
        "equation",
        "equation*",
        "align",
        "align*",
        "gather",
        "gather*",
        "multline",
        "multline*",
        "displaymath",
        "itemize",
        "enumerate",
        "description",
        "quote",
        "quotation",
        "verse",
        "minipage",
        "center",
        "flushleft",
        "flushright",
        "answerfigure",
        "solutionfigure",
        "bookanswerfigure",
        "booksolutionfigure",
    }
)

DEFAULT_ANSWER_OWNER_ENVIRONMENTS = frozenset(
    {
        "bookanswer",
        "booksolution",
        "bookanalysis",
        "bookhint",
        "bookmethodstep",
        "bookproofstep",
        "bookanalysisstep",
        "booksolutionstep",
        "bookcase",
    }
)

DEFAULT_QUESTION_OWNER_ENVIRONMENTS = frozenset(
    {
        "bookexample",
        "bookexamplestart",
        "bookexamplecontinuation",
        "bookexampleend",
        "bookexercise",
        "bookexercisestart",
        "bookexercisecontinuation",
        "bookexerciseend",
        "bookquestion",
        "bookquestionstart",
        "bookquestioncontinuation",
        "bookquestionend",
    }
)

DEFAULT_ANSWER_MEDIA_ENVIRONMENTS = frozenset(
    {"answerfigure", "solutionfigure", "bookanswerfigure", "booksolutionfigure"}
)

KNOWLEDGE_STEPS = {
    "bookknowledgeblockopen": ("knowledge", "start"),
    "bookknowledgeblockmiddle": ("knowledge", "middle"),
    "bookknowledgeblockcontinued": ("knowledge", "end"),
    "knowledgeblockopen": ("knowledge", "start"),
    "knowledgeblockmiddle": ("knowledge", "middle"),
    "knowledgeblockcontinued": ("knowledge", "end"),
    "bookknowledgeopen": ("knowledge", "start"),
    "bookknowledgemiddle": ("knowledge", "middle"),
    "bookknowledgecontinued": ("knowledge", "end"),
}

QUESTION_STEPS = {
    "bookexamplestart": ("example", "start"),
    "bookexamplecontinuation": ("example", "middle"),
    "bookexampleend": ("example", "end"),
    "bookexercisestart": ("exercise", "start"),
    "bookexercisecontinuation": ("exercise", "middle"),
    "bookexerciseend": ("exercise", "end"),
    "bookquestionstart": ("question", "start"),
    "bookquestioncontinuation": ("question", "middle"),
    "bookquestionend": ("question", "end"),
}


@dataclass(frozen=True)
class AuditConfig:
    owner_environments: frozenset[str]
    owner_parent_environments: dict[str, frozenset[str]]
    structure_commands: frozenset[str]
    media_environments: frozenset[str]
    answer_owner_environments: frozenset[str]
    question_owner_environments: frozenset[str]
    answer_media_environments: frozenset[str]


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    column: int
    code: str
    message: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class Event:
    path: str
    line: int
    column: int
    name: str


@dataclass(frozen=True)
class PageAudit:
    path: Path
    relative_path: str
    owner_events: tuple[Event, ...]


@dataclass(frozen=True)
class EnvironmentFrame:
    name: str
    line: int
    column: int
    is_owner: bool


@dataclass(frozen=True)
class SequenceState:
    family: str
    event: Event


class ConfigurationError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="审计 latex/front、latex/pages 和 latex/back 的语义所有权；不读取 PDF 或页图。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument(
        "--files",
        nargs="+",
        type=Path,
        metavar="PAGE",
        help="只报告这些逐页文件的问题；可使用绝对路径或项目根目录的相对路径",
    )
    parser.add_argument(
        "--json", action="store_true", help="输出一份机器可读的 JSON 报告"
    )
    return parser.parse_args()


def _configured_set(
    payload: dict[str, Any], key: str, default: frozenset[str], pattern: re.Pattern[str]
) -> frozenset[str]:
    if key not in payload:
        return default
    value = payload[key]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigurationError(f"{key} 必须是字符串数组")
    normalized: list[str] = []
    for item in value:
        name = item[1:] if key == "structure_commands" and item.startswith("\\") else item
        if pattern.fullmatch(name) is None:
            raise ConfigurationError(f"{key} 中的名称无效: {item!r}")
        normalized.append(name)
    if len(normalized) != len(set(normalized)):
        raise ConfigurationError(f"{key} 包含重复名称")
    return frozenset(normalized)


def _configured_owner_parents(
    payload: dict[str, Any], owner_environments: frozenset[str]
) -> dict[str, frozenset[str]]:
    """Read an optional direct-parent allowlist for semantic owners.

    Keys are child owner environments. Values contain owner environments or the
    ``$root`` sentinel for a root owner. Omitted children stay unconstrained so
    a project can introduce this check incrementally while its class API grows.
    """
    key = "owner_parent_environments"
    if key not in payload:
        return {}
    value = payload[key]
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} 必须是对象")

    normalized: dict[str, frozenset[str]] = {}
    for child, parents in value.items():
        if not isinstance(child, str) or child not in owner_environments:
            raise ConfigurationError(
                f"{key} 中的子所有者必须属于 owner_environments: {child!r}"
            )
        if not isinstance(parents, list) or not parents:
            raise ConfigurationError(f"{key}.{child} 必须是非空字符串数组")

        parent_names: list[str] = []
        for parent in parents:
            if not isinstance(parent, str):
                raise ConfigurationError(f"{key}.{child} 包含非字符串父所有者")
            if parent == ROOT_OWNER:
                parent_names.append(parent)
                continue
            if parent not in owner_environments:
                raise ConfigurationError(
                    f"{key}.{child} 中的父所有者未登记: {parent!r}"
                )
            parent_names.append(parent)
        if len(parent_names) != len(set(parent_names)):
            raise ConfigurationError(f"{key}.{child} 包含重复父所有者")
        normalized[child] = frozenset(parent_names)
    return normalized


def load_config(project: Path) -> tuple[AuditConfig, Path | None]:
    config_path = project / CONTROL_DIR / CONFIG_FILENAME
    payload: dict[str, Any] = {}
    loaded_path: Path | None = None
    if config_path.exists():
        if not config_path.is_file():
            raise ConfigurationError(f"配置路径不是文件: {config_path}")
        try:
            value = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"无法读取配置 {config_path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ConfigurationError("配置顶层必须是 JSON 对象")
        allowed = {
            "owner_environments",
            "owner_parent_environments",
            "structure_commands",
            "media_environments",
            "answer_owner_environments",
            "question_owner_environments",
            "answer_media_environments",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ConfigurationError(f"配置包含未知键: {sorted(unknown)}")
        payload = value
        loaded_path = config_path

    owner_environments = _configured_set(
        payload, "owner_environments", DEFAULT_OWNER_ENVIRONMENTS, ENVIRONMENT_NAME
    )
    config = AuditConfig(
        owner_environments=owner_environments,
        owner_parent_environments=_configured_owner_parents(payload, owner_environments),
        structure_commands=_configured_set(
            payload, "structure_commands", DEFAULT_STRUCTURE_COMMANDS, COMMAND_NAME
        ),
        media_environments=_configured_set(
            payload, "media_environments", DEFAULT_MEDIA_ENVIRONMENTS, ENVIRONMENT_NAME
        ),
        answer_owner_environments=_configured_set(
            payload,
            "answer_owner_environments",
            DEFAULT_ANSWER_OWNER_ENVIRONMENTS,
            ENVIRONMENT_NAME,
        ),
        question_owner_environments=_configured_set(
            payload,
            "question_owner_environments",
            DEFAULT_QUESTION_OWNER_ENVIRONMENTS,
            ENVIRONMENT_NAME,
        ),
        answer_media_environments=_configured_set(
            payload,
            "answer_media_environments",
            DEFAULT_ANSWER_MEDIA_ENVIRONMENTS,
            ENVIRONMENT_NAME,
        ),
    )
    missing_answers = config.answer_owner_environments - config.owner_environments
    missing_questions = config.question_owner_environments - config.owner_environments
    missing_answer_media = config.answer_media_environments - config.media_environments
    if missing_answers:
        raise ConfigurationError(
            "answer_owner_environments 也必须属于 owner_environments: "
            f"{sorted(missing_answers)}"
        )
    if missing_questions:
        raise ConfigurationError(
            "question_owner_environments 也必须属于 owner_environments: "
            f"{sorted(missing_questions)}"
        )
    if missing_answer_media:
        raise ConfigurationError(
            "answer_media_environments 也必须属于 media_environments: "
            f"{sorted(missing_answer_media)}"
        )
    return config, loaded_path


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


def audit_page(
    path: Path,
    project: Path,
    config: AuditConfig,
    issues: list[Issue],
    seen_question: bool,
) -> tuple[PageAudit, bool]:
    relative = path.relative_to(project).as_posix()
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigurationError(f"无法读取 UTF-8 逐页文件 {path}: {exc}") from exc
    text = strip_comments(original)
    newlines = [index for index, character in enumerate(text) if character == "\n"]
    stack: list[EnvironmentFrame] = []
    events: list[Event] = []
    index = 0

    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        if text[index] != "\\":
            end = index + 1
            while end < len(text) and text[end] not in "\\\n":
                end += 1
            if not stack and text[index:end].strip():
                snippet = " ".join(text[index:end].strip().split())[:60]
                add_issue(
                    issues,
                    relative,
                    newlines,
                    index,
                    "bare_text",
                    f"可见文字没有语义所有者: {snippet!r}",
                )
            index = end
            continue

        command_index = index
        command, cursor = read_command(text, index)
        if command in {"begin", "end"}:
            parsed = parse_group(text, cursor, "{", "}")
            if parsed is None:
                add_issue(
                    issues,
                    relative,
                    newlines,
                    command_index,
                    "malformed_environment",
                    f"\\{command} 缺少成对的环境名参数",
                )
                index = cursor
                continue
            environment, index = parsed
            environment = environment.strip()
            if ENVIRONMENT_NAME.fullmatch(environment) is None:
                add_issue(
                    issues,
                    relative,
                    newlines,
                    command_index,
                    "malformed_environment",
                    f"环境名无效: {environment!r}",
                )
                continue
            if command == "end":
                if not stack:
                    add_issue(
                        issues,
                        relative,
                        newlines,
                        command_index,
                        "orphan_environment_end",
                        f"\\end{{{environment}}} 没有匹配的开始环境",
                    )
                elif stack[-1].name != environment:
                    expected = stack[-1]
                    add_issue(
                        issues,
                        relative,
                        newlines,
                        command_index,
                        "mismatched_environment_end",
                        f"应为 \\end{{{expected.name}}}，实际为 \\end{{{environment}}}",
                    )
                    matching = next(
                        (position for position in range(len(stack) - 1, -1, -1) if stack[position].name == environment),
                        None,
                    )
                    if matching is not None:
                        del stack[matching:]
                else:
                    stack.pop()
                continue

            owner_context = any(frame.is_owner for frame in stack)
            direct_owner_parent = next(
                (frame.name for frame in reversed(stack) if frame.is_owner), None
            )
            answer_context = any(
                frame.name in config.answer_owner_environments for frame in stack
            )
            is_owner = environment in config.owner_environments
            is_media = environment in config.media_environments

            # Semantic owners may be nested. When the project registers a
            # direct-parent allowlist, reject any edge outside that tree.
            line, column = line_column(newlines, command_index)

            if is_owner:
                allowed_parents = config.owner_parent_environments.get(environment)
                actual_parent = ROOT_OWNER if direct_owner_parent is None else direct_owner_parent
                if allowed_parents is not None and actual_parent not in allowed_parents:
                    add_issue(
                        issues,
                        relative,
                        newlines,
                        command_index,
                        "owner_parent_not_allowed",
                        f"所有者 {environment!r} 不能直接嵌套在 {actual_parent!r} 内",
                    )

            if is_media and not owner_context and not is_owner:
                add_issue(
                    issues,
                    relative,
                    newlines,
                    command_index,
                    "media_without_owner",
                    f"媒体或布局环境 {environment!r} 没有语义所有者",
                )
            elif not stack and not is_owner:
                add_issue(
                    issues,
                    relative,
                    newlines,
                    command_index,
                    "top_level_environment",
                    f"顶层环境 {environment!r} 未登记为语义所有者",
                )

            if environment in config.answer_media_environments and not answer_context:
                add_issue(
                    issues,
                    relative,
                    newlines,
                    command_index,
                    "answer_media_outside_answer",
                    f"答案专属媒体 {environment!r} 位于答案所有者之外",
                )
            if environment in config.answer_owner_environments:
                if not seen_question:
                    add_issue(
                        issues,
                        relative,
                        newlines,
                        command_index,
                        "answer_without_question",
                        f"答案所有者 {environment!r} 出现在所有题目所有者之前",
                    )
            if environment in config.question_owner_environments:
                if answer_context:
                    add_issue(
                        issues,
                        relative,
                        newlines,
                        command_index,
                        "question_inside_answer",
                        f"题目所有者 {environment!r} 嵌套在答案所有者内",
                    )
                seen_question = True
            if not stack and is_owner:
                events.append(Event(relative, line, column, environment))
            stack.append(EnvironmentFrame(environment, line, column, is_owner))
            continue

        if not stack:
            if command in config.structure_commands:
                index, complete = consume_command_arguments(text, cursor, required=1)
                if not complete:
                    add_issue(
                        issues,
                        relative,
                        newlines,
                        command_index,
                        "malformed_structure_command",
                        f"结构命令 \\{command} 需要一个花括号参数",
                    )
                continue
            add_issue(
                issues,
                relative,
                newlines,
                command_index,
                "top_level_command",
                f"顶层命令 \\{command} 未登记为结构命令",
            )
            index, _ = consume_command_arguments(text, cursor, required=1)
            continue
        index = cursor

    for frame in reversed(stack):
        issues.append(
            Issue(
                relative,
                frame.line,
                frame.column,
                "unclosed_environment",
                f"环境 {frame.name!r} 未在本文件内闭合",
            )
        )
    return PageAudit(path, relative, tuple(events)), seen_question


def page_sort_key(path: Path, section_index: int) -> tuple[int, int, str]:
    match = re.search(r"(\d+)(?=\.tex$)", path.name)
    number = int(match.group(1)) if match else sys.maxsize
    return section_index, number, path.name


def collect_pages(project: Path) -> list[Path]:
    latex = project / "latex"
    sections = ("front", "pages", "back")
    pages: list[Path] = []
    for section_index, section in enumerate(sections):
        directory = latex / section
        if not directory.is_dir():
            raise ConfigurationError(f"缺少逐页目录: {directory}")
        section_pages = [path for path in directory.glob("*.tex") if path.is_file()]
        pages.extend(sorted(section_pages, key=lambda path: page_sort_key(path, section_index)))
    if not pages:
        raise ConfigurationError("三个逐页目录中没有找到直接子级 .tex 文件")
    return pages


def audit_sequence(
    pages: list[PageAudit],
    steps: dict[str, tuple[str, str]],
    label: str,
    issues: list[Issue],
) -> None:
    state: SequenceState | None = None
    for page in pages:
        events = page.owner_events
        if state is not None:
            first = events[0] if events else None
            first_step = steps.get(first.name) if first is not None else None
            if first_step is None or first_step[0] != state.family or first_step[1] not in {
                "middle",
                "end",
            }:
                issues.append(
                    Issue(
                        state.event.path,
                        state.event.line,
                        state.event.column,
                        f"missing_{label}_continuation",
                        f"{page.relative_path} 页首缺少 {state.family} 的续段或结束段",
                    )
                )
                state = None

        for position, event in enumerate(events):
            step = steps.get(event.name)
            if step is None:
                continue
            family, phase = step
            if phase == "start":
                if state is not None:
                    issues.append(
                        Issue(
                            event.path,
                            event.line,
                            event.column,
                            f"overlapping_{label}_sequence",
                            f"{event.name!r} 在上一个 {state.family} 跨页序列结束前再次开始",
                        )
                    )
                state = SequenceState(family, event)
            elif state is None or state.family != family:
                issues.append(
                    Issue(
                        event.path,
                        event.line,
                        event.column,
                        f"orphan_{label}_{phase}",
                        f"{event.name!r} 没有匹配的 {family} 开始段",
                    )
                )
                continue
            elif state.event.path == event.path:
                issues.append(
                    Issue(
                        event.path,
                        event.line,
                        event.column,
                        f"same_file_{label}_{phase}",
                        f"{event.name!r} 必须续接前一个逐页文件中的序列",
                    )
                )
                if phase == "end":
                    state = None
                else:
                    state = SequenceState(family, event)
            elif phase == "end":
                state = None
            else:
                state = SequenceState(family, event)

            if phase in {"start", "middle"} and position != len(events) - 1:
                issues.append(
                    Issue(
                        event.path,
                        event.line,
                        event.column,
                        f"{label}_segment_not_last",
                        f"{event.name!r} 必须是本页最后一个顶层所有者",
                    )
                )

    if state is not None:
        issues.append(
            Issue(
                state.event.path,
                state.event.line,
                state.event.column,
                f"unclosed_{label}_sequence",
                f"{state.family} 跨页序列缺少结束段",
            )
        )


def audit_project(project: Path, config: AuditConfig) -> tuple[list[Path], list[Issue]]:
    pages = collect_pages(project)
    issues: list[Issue] = []
    audits: list[PageAudit] = []
    seen_question = False
    for path in pages:
        audit, seen_question = audit_page(path, project, config, issues, seen_question)
        audits.append(audit)
    audit_sequence(audits, KNOWLEDGE_STEPS, "knowledge", issues)
    audit_sequence(audits, QUESTION_STEPS, "question", issues)
    issues.sort(key=lambda item: (item.path, item.line, item.column, item.code))
    return pages, issues


def select_report_files(project: Path, pages: list[Path], requested: list[Path] | None) -> set[str]:
    if requested is None:
        return {path.relative_to(project).as_posix() for path in pages}

    allowed = {path.resolve(): path.relative_to(project).as_posix() for path in pages}
    selected: set[str] = set()
    for item in requested:
        candidate = item if item.is_absolute() else project / item
        resolved = candidate.resolve()
        relative = allowed.get(resolved)
        if relative is None:
            raise ConfigurationError(
                f"所选路径不是本项目逐页目录的直接子级 .tex 文件: {item}"
            )
        if relative in selected:
            raise ConfigurationError(f"所选文件重复: {item}")
        selected.add(relative)
    return selected


def emit_error(project: Path, message: str, json_output: bool) -> None:
    if json_output:
        print(
            json.dumps(
                {
                    "ok": False,
                    "project": str(project),
                    "files_audited": 0,
                    "issues": [],
                    "error": {"code": "configuration_error", "message": message},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"语义审计配置错误: {message}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        emit_error(project, f"项目目录不存在: {project}", args.json)
        return 2
    try:
        config, config_path = load_config(project)
        pages, issues = audit_project(project, config)
        selected = select_report_files(project, pages, args.files)
        issues = [issue for issue in issues if issue.path in selected]
    except ConfigurationError as exc:
        emit_error(project, str(exc), args.json)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not issues,
                    "project": str(project),
                    "configuration": str(config_path) if config_path else None,
                    "files_audited": len(selected),
                    "files_scanned_for_context": len(pages),
                    "issues": [issue.as_dict() for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif issues:
        for issue in issues:
            print(
                f"{issue.path}:{issue.line}:{issue.column}: "
                f"{issue.code}: {issue.message}"
            )
        print(f"语义审计未通过：{len(selected)} 个文件中发现 {len(issues)} 个问题")
    else:
        suffix = f"；配置 {config_path}" if config_path else ""
        print(f"语义审计通过：{len(selected)} 个文件{suffix}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
