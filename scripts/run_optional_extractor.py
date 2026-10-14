#!/usr/bin/env python3
"""在受控范围内运行可选 PDF 提取器，生成候选证据清单。

这个脚本不是正文转换器。它只允许对明确的页范围运行已安装的候选工具，
把 stdout/stderr 和工具输出放进项目 ``tmp/tool-probes/``，并生成一份不含正文
内容的 manifest。任何 Markdown、JSON、LaTeX、公式或图片都是候选，必须经过
逐页视觉复核后才能被吸收到项目源码；本脚本不会修改 ``latex/``、``docs/`` 或样式卡片。

示例::

    python -X utf8 scripts/run_optional_extractor.py PROJECT INPUT.pdf \
      --tool mineru --pages 12-14 --output tmp/tool-probes/mineru/p012-014

``--pages`` 使用从 1 开始的 PDF 页号。默认不接受全书范围；如果确实要对全书做
候选探查，必须显式传 ``--all-pages``，并且仍然只把结果写进 ``tmp/``。即使全书
运行，MinerU 也保留 ``--limit``，避免把候选正文直接变成无界的上下文输入。运行器
还会轮询输出目录，在达到文件、单文件或总量上限时提前终止候选进程。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import mineru_env  # noqa: E402


SCHEMA = "optional-extractor-run.v2"
TOOLS = ("mineru", "marker", "docling")
PAGE_TOKEN = re.compile(r"^(\d+)(?:-(\d+))?$")
DEFAULT_MAX_OUTPUT_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_OUTPUT_FILES = 256
DEFAULT_MAX_OUTPUT_TOTAL_BYTES = 128 * 1024 * 1024
MAX_OVERSIZED_REPORT = 64
RUNNER_LOG_NAMES = {"run.stdout.log", "run.stderr.log"}


class UsageError(RuntimeError):
    """参数或输出位置违反候选工具契约。"""


class ToolUnavailable(RuntimeError):
    """当前环境没有可运行的候选工具。"""


def cli_help_contract(tool: str, executable: str) -> tuple[list[str], tuple[str, ...]]:
    """Return a help command and the tokens required by the selected adapter."""

    if tool == "mineru":
        if Path(executable).stem.lower().startswith("mineru-kit"):
            # 无状态批处理入口：直接写文件，不需要常驻服务。
            return [executable, "parse", "--help"], ("--pages", "--format", "--output")
        return [executable, "parse", "--help"], ("--pages", "--json", "--limit")
    if tool == "marker":
        return [executable, "--help"], ("--page_range", "--output_format", "--output_dir")
    if tool == "docling":
        return [executable, "convert", "--help"], ("--page-range", "--to", "--output")
    raise UsageError(f"没有 CLI 契约: {tool}")


def verify_cli_contract(tool: str, executable: str) -> dict[str, object]:
    """Verify the adapter against the installed CLI before reading a document."""

    command, required = cli_help_contract(tool, executable)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolUnavailable(
            f"{tool} 的 CLI 契约探测失败: {type(exc).__name__}；拒绝运行候选转换。"
        ) from exc
    help_text = f"{result.stdout}\n{result.stderr}"
    missing = [token for token in required if token not in help_text]
    if result.returncode != 0 or missing:
        detail = f"缺少参数 {', '.join(missing)}" if missing else f"返回码 {result.returncode}"
        raise ToolUnavailable(
            f"{tool} 的已安装 CLI 与当前适配器不匹配（{detail}）；"
            "请先更新适配器或把该工具降级为只读探针。"
        )
    encoded = help_text.encode("utf-8", errors="replace")
    return {
        "verified": True,
        "command": command,
        "returncode": result.returncode,
        "required_tokens": list(required),
        "help_bytes": len(encoded),
        "help_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="在 tmp/tool-probes/ 内受控运行 MinerU/Marker/Docling 结构候选工具。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument("input_pdf", type=Path, help="待探查的 PDF；只读，不会修改")
    parser.add_argument("--tool", choices=TOOLS, required=True)
    parser.add_argument(
        "--pages",
        default=None,
        help="从 1 开始的页范围，如 12-14,18；不传时必须使用 --all-pages",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="显式允许候选工具处理全书；仍不写入交付目录",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="输出目录；必须位于 PROJECT/tmp/tool-probes/ 下",
    )
    parser.add_argument("--timeout", type=int, default=600, help="最长运行秒数（默认 600）")
    parser.add_argument(
        "--context-limit",
        type=int,
        default=12000,
        help="MinerU JSON/stdout 候选的字符上限（默认 12000；其它工具忽略）",
    )
    parser.add_argument(
        "--max-output-bytes",
        type=int,
        default=DEFAULT_MAX_OUTPUT_BYTES,
        help=(
            "单个候选输出文件的字节上限；超限标记为 oversize 并拒绝放行 "
            f"（默认 {DEFAULT_MAX_OUTPUT_BYTES}）"
        ),
    )
    parser.add_argument(
        "--max-output-files",
        type=int,
        default=DEFAULT_MAX_OUTPUT_FILES,
        help=(
            "候选输出文件数量上限；超限标记为 oversize 并拒绝放行 "
            f"（默认 {DEFAULT_MAX_OUTPUT_FILES}）"
        ),
    )
    parser.add_argument(
        "--max-output-total-bytes",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOTAL_BYTES,
        help=(
            "候选输出总字节上限；超限标记为 oversize 并拒绝放行 "
            f"（默认 {DEFAULT_MAX_OUTPUT_TOTAL_BYTES}）"
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="只生成命令计划，不执行工具")
    parser.add_argument(
        "--mineru-exe",
        default=None,
        help="显式指定 MinerU 可执行文件（优先于环境变量与项目配置；仅 --tool mineru 生效）",
    )
    return parser.parse_args()


def parse_pages(value: str | None, all_pages: bool) -> tuple[list[int] | None, str]:
    if all_pages:
        if value:
            raise UsageError("--pages 与 --all-pages 不能同时使用")
        return None, "all"
    if not value:
        raise UsageError("必须提供 --pages；全书探查请显式使用 --all-pages")
    result: list[int] = []
    for token in value.split(","):
        match = PAGE_TOKEN.fullmatch(token.strip())
        if not match:
            raise UsageError(f"非法页范围: {token!r}（示例：12-14,18）")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start:
            raise UsageError(f"页范围必须从 1 开始且起点不大于终点: {token!r}")
        result.extend(range(start, end + 1))
    pages = sorted(set(result))
    if not pages:
        raise UsageError("页范围不能为空")
    return pages, ",".join(str(page) for page in pages)


def compact_page_ranges(pages: list[int] | None) -> str:
    """把已展开且排序的页号压成 ``1-3,8`` 形式。"""

    if pages is None:
        return "all"
    if not pages:
        raise UsageError("页范围不能为空")
    groups: list[str] = []
    start = previous = pages[0]
    for page in pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        groups.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = page
    groups.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(groups)


def marker_page_range(pages: list[int] | None) -> str:
    """Marker 的 ``--page_range`` 使用从 0 开始的页号。"""

    if pages is None:
        return "all"
    return compact_page_ranges([page - 1 for page in pages])


def docling_page_range(pages: list[int] | None) -> str | None:
    """Docling 适配器只接受一个连续的 1-based 区间。"""

    if pages is None:
        return None
    expected = list(range(pages[0], pages[-1] + 1))
    if pages != expected:
        raise UsageError(
            "Docling 的统一运行器只接受连续页范围；请把非连续页拆成多次运行，"
            "避免工具静默忽略或误解页号。"
        )
    return str(pages[0]) if len(pages) == 1 else f"{pages[0]}-{pages[-1]}"


def resolve_executable(
    tool: str, pages: list[int] | None, project: Path, explicit: str | None = None
) -> tuple[str, str, dict[str, object] | None]:
    """只选择已经确认过页范围语义的入口，未知旧入口按不可用处理。

    MinerU 走共享发现顺序（显式参数 → 环境变量 → 项目配置 → PATH → 常见虚拟
    环境），因为它通常装在独立 venv 里、不在 PATH 上。其余工具仍只用 PATH。
    """

    if tool == "mineru":
        # MinerU 4.x 有两个 parse 入口，行为不同：
        #   mineru       —— 常驻服务客户端，需要先 ``mineru server start``
        #   mineru-kit   —— 无状态批处理，直接写文件（本技能的实际运行方式）
        # 优先用无状态入口：候选运行器不该要求用户先起一个守护进程，而且
        # 无状态入口把结果直接写进我们指定的 tmp/ 目录，边界更清楚。
        try:
            candidate = mineru_env.locate_or_raise(project, explicit=explicit)
        except mineru_env.MineruEnvError as exc:
            raise ToolUnavailable(str(exc)) from exc
        kit = mineru_env.sibling_executable(candidate.path, "mineru-kit")
        chosen = kit or candidate.path
        resolved = {
            "path": str(chosen),
            "source": candidate.source,
            "entrypoint": "mineru-kit" if kit else "mineru",
            "version": mineru_env.version_of(candidate.path, timeout=4.0),
        }
        if kit is None:
            resolved["warning"] = (
                "未发现同目录的 mineru-kit；回退到 mineru parse，"
                "它需要先运行 `mineru server start`。"
            )
        return str(chosen), chosen.name, resolved
    if tool == "marker":
        # marker_single 是单文档 CLI；旧的 marker 入口参数并不稳定。
        candidates = ("marker_single",)
    else:
        candidates = ("docling",)
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path, candidate, None
    raise ToolUnavailable(
        f"未发现 {tool} 的受支持 CLI；本次范围需要: {', '.join(candidates)}。"
        "旧版 magic-pdf/marker 入口不会被自动调用。"
    )


def build_command(
    tool: str,
    executable: str,
    executable_name: str,
    input_pdf: Path,
    pages: list[int] | None,
    output: Path,
    context_limit: int,
) -> list[str]:
    page_text = compact_page_ranges(pages)
    if tool == "mineru":
        if Path(executable).stem.lower().startswith("mineru-kit"):
            # 无状态入口：直接把 markdown 写进候选目录。它不需要常驻服务，
            # 也不会把整份候选正文倒进 stdout（那会瞬间吃掉上下文）。
            return [
                executable,
                "parse",
                str(input_pdf),
                "--pages",
                page_text if pages is not None else "all",
                "--format",
                "markdown",
                "--output",
                str(output / "candidate.md"),
            ]
        # ``mineru parse`` 是服务客户端：JSON 候选走 stdout，由运行器重定向到
        # tmp/ 下的 run.stdout.log。``all`` 仍受 --limit 约束，它不是"把整份
        # 候选读进上下文"的许可。
        return [
            executable,
            "parse",
            str(input_pdf),
            "--pages",
            page_text if pages is not None else "all",
            "--json",
            "--limit",
            str(context_limit),
        ]
    if tool == "marker":
        command = [executable, str(input_pdf)]
        if pages is not None:
            command.extend(("--page_range", marker_page_range(pages)))
        command.extend(("--output_format", "json", "--output_dir", str(output)))
        return command
    if tool == "docling":
        # The current CLI keeps conversion under the explicit ``convert``
        # subcommand.  Keeping it here also makes an old top-level wrapper fail
        # visibly instead of accidentally invoking a different command.
        command = [executable, "convert", str(input_pdf), "--to", "json", "--to", "md"]
        docling_range = docling_page_range(pages)
        if docling_range is not None:
            command.extend(("--page-range", docling_range))
        command.extend(("--output", str(output)))
        return command
    raise UsageError(f"没有命令配置: {tool}")


def ensure_output(project: Path, output: Path) -> Path:
    root = (project / "tmp" / "tool-probes").resolve()
    resolved = (project / output if not output.is_absolute() else output).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        # 同时给出项目相对形式和绝对形式：调用方通常按文档里的
        # ``tmp/tool-probes/`` 思考，而绝对路径才是脚本实际校验的目标。
        relative_root = "tmp/tool-probes"
        raise UsageError(
            f"候选工具输出只能写入 {relative_root}（绝对路径 {root}）下: {resolved}"
        ) from exc
    if resolved == root:
        raise UsageError("请为本次探查指定独立输出目录")
    if resolved.exists() and any(resolved.iterdir()):
        raise UsageError(f"输出目录必须为空: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def file_digest(path: Path) -> str:
    """Stream hashes so a large candidate image never enters memory at once."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_manifest(
    root: Path,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    max_output_files: int = DEFAULT_MAX_OUTPUT_FILES,
    max_output_total_bytes: int = DEFAULT_MAX_OUTPUT_TOTAL_BYTES,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Summarize candidate files without pulling their contents into context.

    Oversized files are recorded by path and size but are not hashed.  The
    manifest itself is capped as well, so a parser that accidentally emits
    thousands of page assets cannot turn a status report into another context
    overflow.
    """

    files: list[dict[str, object]] = []
    oversized: list[dict[str, object]] = []
    oversized_file_count = 0
    all_entries = sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and item.name != "manifest.json"
    )
    candidate_files = [path for path in all_entries if path.name not in RUNNER_LOG_NAMES]
    log_bytes = sum(path.stat().st_size for path in all_entries if path.name in RUNNER_LOG_NAMES)
    candidate_total_bytes = 0
    for path in candidate_files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        candidate_total_bytes += size
        is_oversized = size > max_output_bytes
        if is_oversized:
            oversized_file_count += 1
            if len(oversized) < MAX_OVERSIZED_REPORT:
                oversized.append({"path": relative, "bytes": size})
        if len(files) >= max_output_files:
            continue
        files.append(
            {
                "path": relative,
                "bytes": size,
                "sha256": None if is_oversized else file_digest(path),
            }
        )
    total_bytes = candidate_total_bytes + log_bytes
    return files, {
        "file_count": len(candidate_files),
        "candidate_total_bytes": candidate_total_bytes,
        "log_bytes": log_bytes,
        "total_bytes": total_bytes,
        "max_total_bytes": max_output_total_bytes,
        "manifest_truncated": len(files) < len(candidate_files),
        "oversized_files": oversized,
        "oversized_file_count": oversized_file_count,
        "oversized_report_truncated": oversized_file_count > len(oversized),
        "total_bytes_exceeded": total_bytes > max_output_total_bytes,
        "violates_limits": (
            oversized_file_count > 0
            or len(candidate_files) > max_output_files
            or total_bytes > max_output_total_bytes
        ),
    }


def output_usage(root: Path) -> tuple[int, int, int]:
    """Return candidate count, total bytes, and largest candidate file size.

    This lightweight poller deliberately excludes the future manifest and does
    not hash or read file contents. Runner logs count toward total bytes, but
    they do not consume the candidate file-count limit.
    """

    candidate_count = 0
    total_bytes = 0
    largest_candidate = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.name == "manifest.json":
            continue
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            # A tool may rotate or replace a file between discovery and stat.
            continue
        total_bytes += size
        if path.name in RUNNER_LOG_NAMES:
            continue
        candidate_count += 1
        largest_candidate = max(largest_candidate, size)
    return candidate_count, total_bytes, largest_candidate


def run(args: argparse.Namespace) -> int:
    project = args.project.resolve()
    input_pdf = args.input_pdf.resolve()
    if not project.is_dir():
        raise UsageError(f"项目目录不存在: {project}")
    if not input_pdf.is_file() or input_pdf.suffix.lower() != ".pdf":
        raise UsageError(f"输入必须是存在的 PDF 文件: {input_pdf}")
    if args.timeout < 1:
        raise UsageError("--timeout 必须是正整数")
    if args.context_limit < 1:
        raise UsageError("--context-limit 必须是正整数")
    if args.max_output_bytes < 1:
        raise UsageError("--max-output-bytes 必须是正整数")
    if args.max_output_files < 1:
        raise UsageError("--max-output-files 必须是正整数")
    if args.max_output_total_bytes < 1:
        raise UsageError("--max-output-total-bytes 必须是正整数")

    pages, page_text = parse_pages(args.pages, args.all_pages)
    output = ensure_output(project, args.output)
    executable, executable_name, mineru_executable = resolve_executable(
        args.tool, pages, project, args.mineru_exe
    )
    command = build_command(
        args.tool,
        executable,
        executable_name,
        input_pdf,
        pages,
        output,
        args.context_limit,
    )
    cli_contract = (
        {"verified": False, "reason": "dry-run"}
        if args.dry_run
        else verify_cli_contract(args.tool, executable)
    )
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "tool": args.tool,
        "executable": executable_name,
        "mineru_executable": mineru_executable,
        "input_name": input_pdf.name,
        "pages": page_text,
        "command": command,
        "context_limit": args.context_limit if args.tool == "mineru" else None,
        "output_limits": {
            "max_file_bytes": args.max_output_bytes,
            "max_files": args.max_output_files,
            "max_total_bytes": args.max_output_total_bytes,
        },
        "candidate_only": True,
        "accepted_as_final_source": False,
        "cli_contract": cli_contract,
        "status": "planned" if args.dry_run else "started",
        "outputs": [],
    }
    if args.dry_run:
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    stdout_log = output / "run.stdout.log"
    stderr_log = output / "run.stderr.log"
    started = time.monotonic()
    termination_reason: str | None = None
    with stdout_log.open("w", encoding="utf-8", newline="\n") as stdout, stderr_log.open(
        "w", encoding="utf-8", newline="\n"
    ) as stderr:
        process = subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            # Keep relative side effects inside the already-validated probe
            # directory.  The PDF and all explicit output paths are absolute.
            cwd=output,
            shell=False,
        )
        deadline = time.monotonic() + args.timeout
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            candidate_count, total_bytes, largest_candidate = output_usage(output)
            if (
                candidate_count > args.max_output_files
                or largest_candidate > args.max_output_bytes
                or total_bytes > args.max_output_total_bytes
            ):
                process.kill()
                process.wait()
                termination_reason = "output_limit"
                returncode = process.returncode
                break
            if time.monotonic() >= deadline:
                process.kill()
                process.wait()
                termination_reason = "timeout"
                returncode = None
                break
            time.sleep(0.1)

    outputs, output_summary = file_manifest(
        output,
        max_output_bytes=args.max_output_bytes,
        max_output_files=args.max_output_files,
        max_output_total_bytes=args.max_output_total_bytes,
    )
    if termination_reason == "output_limit":
        status = "oversize"
    elif termination_reason == "timeout":
        status = "timeout"
    elif returncode != 0:
        status = "failed"
    elif output_summary["violates_limits"]:
        status = "oversize"
    else:
        status = "ok"
    manifest.update(
        {
            "status": status,
            "returncode": returncode,
            "termination_reason": termination_reason,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stdout_log": stdout_log.name,
            "stderr_log": stderr_log.name,
            "outputs": outputs,
            "output_summary": output_summary,
        }
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "tool": args.tool,
                "status": manifest["status"],
                "returncode": manifest.get("returncode"),
                "pages": page_text,
                "output_dir": str(output),
                "output_count": len(manifest["outputs"]),
                "manifest": str(output / "manifest.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if status == "ok" else 1


def main() -> int:
    try:
        return run(parse_args())
    except (UsageError, ToolUnavailable) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
