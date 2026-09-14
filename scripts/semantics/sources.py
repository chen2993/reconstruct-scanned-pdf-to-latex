"""收集逐页源码并审计语义所有权与跨页结构。"""

from __future__ import annotations

import re
from pathlib import Path

from .defaults import ENVIRONMENT_NAME, MODULE_FILENAME, PAGE_LIKE_MODULE
from .models import AuditConfig, ConfigurationError, EnvironmentFrame, Issue
from .paths import ROOT_OWNER
from .texparse import (
    add_issue,
    consume_command_arguments,
    line_column,
    parse_group,
    read_command,
    strip_comments,
)


def audit_source(
    path: Path,
    project: Path,
    config: AuditConfig,
    issues: list[Issue],
    stack: list[EnvironmentFrame],
    seen_question: bool,
) -> bool:
    """Audit one source file while preserving the project-wide environment stack."""
    relative = path.relative_to(project).as_posix()
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigurationError(f"无法读取 UTF-8 逐页文件 {path}: {exc}") from exc
    text = strip_comments(original)
    newlines = [index for index, character in enumerate(text) if character == "\n"]
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
            if (
                environment in config.answer_owner_environments
                and not seen_question
            ):
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
            stack.append(EnvironmentFrame(environment, relative, line, column, is_owner))
            continue

        if command in config.forbidden_commands:
            add_issue(
                issues,
                relative,
                newlines,
                command_index,
                "hardcoded_command",
                f"\\{command} 属于 .cls 的集中职责，不得出现在逐页或前后置源码中",
            )
            index, _ = consume_command_arguments(text, cursor, required=1)
            continue

        if not stack:
            if command in config.standalone_commands:
                # 集中接口的参数形状各不相同（0 到多个花括号参数），
                # 因此只贪心吞掉紧随的花括号组，不要求固定形状。
                while True:
                    group = parse_group(text, cursor, "{", "}")
                    if group is None:
                        break
                    _, cursor = group
                index = cursor
                continue
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

    return seen_question


def collect_pages(project: Path) -> list[Path]:
    latex = project / "latex"
    main = latex / "main.tex"
    if not main.is_file():
        raise ConfigurationError(f"缺少唯一入口: {main}")
    for section in ("front", "pages", "back"):
        directory = latex / section
        if not directory.is_dir():
            raise ConfigurationError(f"缺少逐页目录: {directory}")

    try:
        source = main.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigurationError(f"无法读取入口 {main}: {exc}") from exc
    source = strip_comments(source)
    token_pattern = re.compile(
        r"\\input\s*\{([^{}]+)\}|\\bookinput\s*\{(\d+)\}\s*\{(\d+)\}"
    )
    ordered: list[Path] = []
    seen: set[Path] = set()
    body_ranges: list[tuple[int, int]] = []

    def validate_module_filename(section: str, candidate: Path) -> None:
        stem = candidate.stem
        if MODULE_FILENAME.fullmatch(stem) is None or PAGE_LIKE_MODULE.fullmatch(stem):
            raise ConfigurationError(
                f"{section} 模块必须使用英文语义类型名，禁止页码式名称: {candidate.name}"
            )
        if re.search(r"[-_]\d+$", stem):
            raise ConfigurationError(
                f"{section} 模块名不能以页码式数字结尾: {candidate.name}"
            )

    def add_module(token: str) -> None:
        normalized = token.strip().replace("\\", "/")
        parts = Path(normalized).parts
        if len(parts) != 2 or parts[0] not in {"front", "back"}:
            raise ConfigurationError(
                "main.tex 的前后置必须使用 \\input{front/TYPE} 或 \\input{back/TYPE}；"
                "正文必须使用唯一的 \\bookinput 范围"
            )
        filename = parts[1] if parts[1].endswith(".tex") else f"{parts[1]}.tex"
        candidate = latex / parts[0] / filename
        if candidate.parent != latex / parts[0] or not candidate.is_file():
            raise ConfigurationError(f"main.tex 引用的模块不存在或不是直接子级文件: {token}")
        validate_module_filename(parts[0], candidate)
        if candidate in seen:
            raise ConfigurationError(f"main.tex 重复加载模块: {token}")
        seen.add(candidate)
        ordered.append(candidate)

    for match in token_pattern.finditer(source):
        token = match.group(1)
        if token is not None:
            add_module(token)
            continue
        start = int(match.group(2))
        end = int(match.group(3))
        if start != 1 or end < start:
            raise ConfigurationError(
                "main.tex 的正文必须以唯一的 \\bookinput{1}{N} 开始并保持有效范围"
            )
        body_ranges.append((start, end))

    if len(body_ranges) != 1:
        raise ConfigurationError("main.tex 必须包含且只包含一条 \\bookinput{1}{N}")
    _, body_end = body_ranges[0]
    body_directory = latex / "pages"
    width = max(3, len(str(body_end)))
    body_paths: list[Path] = []
    for number in range(1, body_end + 1):
        candidate = body_directory / f"pages-{number:0{width}d}.tex"
        if not candidate.is_file():
            raise ConfigurationError(f"\\bookinput 引用的正文页不存在: {candidate}")
        body_paths.append(candidate)
    actual_body = {
        path
        for path in body_directory.glob("pages-*.tex")
        if path.is_file()
    }
    expected_body = set(body_paths)
    if actual_body != expected_body:
        extras = sorted(actual_body - expected_body)
        if extras:
            raise ConfigurationError(
                "pages 中存在未由唯一 \\bookinput 导入的正文页: "
                + ", ".join(path.name for path in extras)
            )
    ordered.extend(body_paths)

    for section in ("front", "back"):
        directory = latex / section
        actual = {path for path in directory.glob("*.tex") if path.is_file()}
        for candidate in sorted(actual):
            validate_module_filename(section, candidate)
        referenced = {path for path in seen if path.parent == directory}
        missing = sorted(actual - referenced)
        if missing:
            raise ConfigurationError(
                f"{section} 中存在未由 main.tex 导入的模块: "
                + ", ".join(path.name for path in missing)
            )
    return ordered


def audit_file_boundary(
    source: Path,
    project: Path,
    stack: list[EnvironmentFrame],
    config: AuditConfig,
    issues: list[Issue],
) -> None:
    """Require each environment left open by ``source`` to be a streaming owner.

    An open frame remains on ``stack`` so the next source file can supply its
    real ``\\end`` token.  Reporting only frames opened in this source avoids
    repeating the same cross-boundary error on every later file.
    """
    relative = source.relative_to(project).as_posix()
    for frame in stack:
        if frame.path != relative:
            continue
        if frame.is_owner and frame.name in config.cross_page_owner_environments:
            continue
        issues.append(
            Issue(
                frame.path,
                frame.line,
                frame.column,
                "cross_page_environment_not_allowed",
                f"环境 {frame.name!r} 跨越源文件边界；只有 "
                "cross_page_owner_environments 中显式登记的语义所有者可以跨页",
            )
        )


def audit_unclosed_environments(
    stack: list[EnvironmentFrame], issues: list[Issue]
) -> None:
    for frame in reversed(stack):
        issues.append(
            Issue(
                frame.path,
                frame.line,
                frame.column,
                "unclosed_environment",
                f"环境 {frame.name!r} 未在完整源文件流内闭合",
            )
        )


def audit_project(project: Path, config: AuditConfig) -> tuple[list[Path], list[Issue]]:
    pages = collect_pages(project)
    issues: list[Issue] = []
    stack: list[EnvironmentFrame] = []
    seen_question = False
    for index, path in enumerate(pages):
        seen_question = audit_source(path, project, config, issues, stack, seen_question)
        if index < len(pages) - 1:
            audit_file_boundary(path, project, stack, config, issues)
    audit_unclosed_environments(stack, issues)
    source_order = {
        path.relative_to(project).as_posix(): index for index, path in enumerate(pages)
    }
    issues.sort(
        key=lambda item: (
            source_order.get(item.path, len(source_order)),
            item.line,
            item.column,
            item.code,
        )
    )
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
