#!/usr/bin/env python3
"""调度者工具：把正文拆成批次，生成单元任务包，校验批次产出。

本脚本只做确定性的队列与校验；内容转写、样式判断和视觉复核仍由运行环境的
原生多模态能力完成。用法::

    python -X utf8 scripts/orchestrate.py <project> plan [--batch 10]
    python -X utf8 scripts/orchestrate.py <project> next
    python -X utf8 scripts/orchestrate.py <project> verify <batch-id>
    python -X utf8 scripts/orchestrate.py <project> status

状态保存在 ``.reconstruct-scanned-pdf-to-latex/dispatch.json``；任务包写入
``.reconstruct-scanned-pdf-to-latex/dispatch/<batch-id>.md``。
"""

from __future__ import annotations

import argparse
import re
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from page_workspace import CONTROL_DIR  # noqa: E402
from semantics.config import load_config  # noqa: E402
from semantics.models import ConfigurationError  # noqa: E402
from semantics.sources import audit_source, collect_pages  # noqa: E402

DISPATCH_FILE = "dispatch.json"
DISPATCH_DIR = "dispatch"
STYLE_CARD_FILE = "style-cards.md"
PAGE_TYPES_FILE = "page-types.json"


@dataclass
class Batch:
    batch_id: str
    start: int
    end: int

    @property
    def pages(self) -> list[str]:
        return [f"pages-{n:03d}" for n in range(self.start, self.end + 1)]


def control_dir(project: Path) -> Path:
    return project / CONTROL_DIR


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def batch_id(start: int, end: int) -> str:
    return f"b{start:03d}-{end:03d}"


# 正文范围的两种等价写法：类文件的单命令形式，或逐条/范围加载接口。
BODY_RANGE_PATTERNS = (
    re.compile(r"\\bookinput\s*\{\s*(\d+)\s*\}\s*\{\s*(\d+)\s*\}"),
    re.compile(r"\\bookinputpages\s*\{\s*(\d+)\s*\}\s*\{\s*(\d+)\s*\}"),
)

# 入口候选：单入口用 main.tex；形态 B 下做题本入口也能声明同一份正文范围。
ENTRY_CANDIDATES = ("main.tex", "main-workbook.tex")

def body_range(project: Path) -> tuple[int, int]:
    """返回正文页范围，来源是任一声明了该范围的入口文件。

    入口形态由用户选择（单入口 + 类文件开关，或独立做题本入口），正文范围的写法
    也可能不同（``\\bookinput`` 或 ``\\bookinputpages``）。编排器只关心范围本身，
    因此逐个入口、逐个写法去找那唯一一条声明，而不是绑定某个文件名或命令名。
    """

    latex_root = project / "latex"
    found: list[tuple[Path, int, int]] = []
    for name in ENTRY_CANDIDATES:
        entry = latex_root / name
        if not entry.is_file():
            continue
        text = entry.read_text(encoding="utf-8")
        for pattern in BODY_RANGE_PATTERNS:
            for match in pattern.finditer(text):
                found.append((entry, int(match.group(1)), int(match.group(2))))

    if not found:
        candidates = "、".join(f"latex/{name}" for name in ENTRY_CANDIDATES)
        raise ConfigurationError(
            f"找不到正文范围声明；在 {candidates} 中应有一条 "
            "\\bookinput{1}{N} 或 \\bookinputpages{1}{N}"
        )
    if len(found) > 1:
        where = "、".join(sorted({path.name for path, _, _ in found}))
        raise ConfigurationError(f"正文范围声明出现多次（{where}）；只能有一处")

    entry, start, end = found[0]
    if start != 1 or end < start:
        raise ConfigurationError(
            f"{entry.name} 的正文范围必须从 1 开始且有效，当前为 {start}-{end}"
        )
    return start, end


def plan_batches(project: Path, size: int) -> list[Batch]:
    start, end = body_range(project)
    batches: list[Batch] = []
    cursor = start
    while cursor <= end:
        last = min(cursor + size - 1, end)
        batches.append(Batch(batch_id(cursor, last), cursor, last))
        cursor = last + 1
    return batches


@dataclass
class OpenOwners:
    """Owners still open at the end of a source file."""

    registered: list[str]
    unregistered: list[str]


def open_owners_at_boundaries(project: Path) -> dict[str, OpenOwners]:
    """Map source file -> owners left open at its end.

    A batch that starts inside such an owner must inherit the environment
    name, so the next unit cannot invent a new boundary.  Owners that are open
    but *not* registered as cross-page are reported separately: that is an
    audit failure the dispatcher must surface instead of hiding.
    """
    config, _ = load_config(project)
    pages = collect_pages(project)
    stack: list = []
    seen_question = False
    result: dict[str, OpenOwners] = {}
    for path in pages:
        seen_question = audit_source(path, project, config, [], stack, seen_question)
        relative = path.relative_to(project).as_posix()
        owners = [frame.name for frame in stack if frame.is_owner]
        if owners:
            registered = [
                name
                for name in owners
                if name in config.cross_page_owner_environments
            ]
            unregistered = [
                name
                for name in owners
                if name not in config.cross_page_owner_environments
            ]
            result[relative] = OpenOwners(registered, unregistered)
    return result


def style_digest_version(project: Path) -> str:
    path = control_dir(project) / STYLE_CARD_FILE
    if not path.is_file():
        return "未登记"
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lstrip("-").strip()
        if stripped.startswith("样式摘要版本"):
            return stripped.split("：", 1)[-1].strip() or "未登记"
    return "未登记"


def page_types(project: Path) -> dict[str, str]:
    payload = read_json(control_dir(project) / PAGE_TYPES_FILE)
    return {str(k): str(v) for k, v in payload.items()}


def task_packet(
    project: Path, batch: Batch, open_at: dict[str, OpenOwners]
) -> str:
    types = page_types(project)
    pages_dir = project / "latex" / "pages"
    lines = [
        f"# 任务包 {batch.batch_id}",
        "",
        f"- 样式摘要版本: {style_digest_version(project)}",
        f"- 页面范围: pages-{batch.start:03d} 至 pages-{batch.end:03d}（连续 {len(batch.pages)} 页）",
        "- 允许修改的文件（白名单，只写这些）:",
    ]
    for identifier in batch.pages:
        lines.append(f"  - `latex/pages/{identifier}.tex`")
    lines += [
        "- 只读输入: 本页独立 PNG；同时查看上一页与下一页判断跨页承接",
        "- 禁止: OCR、PDF 文字层、联系页/拼接图、修改 `.cls`/`main.tex`/审计配置/样式卡片/Git",
        "",
        "## 页面分型",
        "",
    ]
    for identifier in batch.pages:
        kind = types.get(identifier, "未分型（按代表页判断）")
        mark = "缺文件" if not (pages_dir / f"{identifier}.tex").is_file() else ""
        suffix = f"  {mark}".rstrip()
        lines.append(f"- {identifier}: {kind}{('  ' + suffix) if suffix else ''}")

    # 交接要覆盖所有可能开放的边界：批内页边界，以及本批最后一页到批外下一页。
    boundaries = batch.pages
    lines += ["", "## 跨页交接", ""]
    reported = False
    for identifier in boundaries:
        relative = f"latex/pages/{identifier}.tex"
        owners = open_at.get(relative)
        if owners is None:
            continue
        reported = True
        is_batch_end = identifier == batch.pages[-1]
        scope = "批末，需移交下一批" if is_batch_end else "批内下一文件"
        for name in owners.registered:
            lines.append(
                f"- {identifier} 结束时仍开放 `{name}`（{scope}）："
                "下一单元必须在该环境内继续写，不得另开新环境边界。"
            )
        for name in owners.unregistered:
            lines.append(
                f"- ⚠ {identifier} 结束时 `{name}` 未闭合，且未登记为可跨页所有者："
                "先修正 `semantic-audit.json` 或源码，再继续本批。"
            )
    if not reported:
        lines.append("- 本批没有跨文件开放的语义所有者。")

    lines += [
        "",
        "## 停工反馈",
        "",
        "遇到未登记样式、样式变体或无法表达的版式时，停止该块并在 "
        "`reviews/style-gaps.md` 记录：页面标识、可见特征、候选语义角色、受影响页面。"
        "不得用临时字体、颜色、间距或最相近环境代替。",
        "",
        "## 完成前自检",
        "",
        "1. 每页恰好一个来源页标记，与文件名一致；",
        "2. 通过 `scripts/audit_semantics.py` 的本文件检查；",
        "3. 通过 `scripts/audit_provenance.py`；",
        "4. 编译该批并逐页与原件比对。",
        "",
    ]
    return "\n".join(lines)


def load_state(project: Path) -> dict:
    payload = read_json(control_dir(project) / DISPATCH_FILE)
    payload.setdefault("batches", {})
    # 0 表示不设人为上限：真实上限由运行环境决定，不应由脚本猜一个数字卡死。
    payload.setdefault("concurrency", 0)
    return payload


def save_state(project: Path, payload: dict) -> None:
    write_json(control_dir(project) / DISPATCH_FILE, payload)


def cmd_plan(project: Path, size: int, concurrency: int) -> int:
    """规划批次。``concurrency`` 为 0 表示不设人为上限（推荐）。

    真实并发上限取决于运行环境（能同时跑多少执行单元、上游是否限流），脚本不应
    猜一个数字把它卡死。需要软门时可显式传正整数。
    """

    # 先验证配置，避免把一个坏基线切成批次再让每个单元各自撞墙。
    load_config(project)
    batches = plan_batches(project, size)
    state = load_state(project)
    existing = state.get("batches", {})
    payload = {
        "batch_size": size,
        "concurrency": concurrency,
        "batches": {
            batch.batch_id: {
                "start": batch.start,
                "end": batch.end,
                "status": existing.get(batch.batch_id, {}).get("status", "pending"),
                "notes": existing.get(batch.batch_id, {}).get("notes", ""),
            }
            for batch in batches
        },
    }
    state.update(payload)
    save_state(project, state)
    print(f"已规划 {len(batches)} 个批次（每批 {size} 页）。")
    return 0


def cmd_next(project: Path, count: int, force: bool) -> int:
    """派发待处理批次，并可一次派多个。

    默认**不设人为上限**：``concurrency`` 为 0 时不排队，由调度者按运行环境实际
    能承载的并发自行决定派多少。``--count`` 控制本次派发几个（0 = 全部待处理），
    这样调度者一次调用就能填满流水线，而不是连调多次。
    """
    state = load_state(project)
    batches = state.get("batches") or {}
    if not batches:
        print("尚未规划批次；先运行 plan。", file=sys.stderr)
        return 2
    order = sorted(batches, key=lambda key: batches[key]["start"])
    limit = int(state.get("concurrency", 0) or 0)
    if limit > 0 and not force:
        in_flight = [
            key
            for key in order
            if batches[key]["status"] in {"dispatched", "in_progress"}
        ]
        if len(in_flight) >= limit:
            print(
                f"已有 {len(in_flight)} 个批次未验收（软上限 {limit}）: "
                + ", ".join(in_flight)
                + "；先 verify 再派下一批，或用 --force 越过。",
                file=sys.stderr,
            )
            return 1

    pending = [key for key in order if batches[key]["status"] == "pending"]
    if not pending:
        print("没有待派发的批次。")
        return 0

    chosen_keys = pending if count <= 0 else pending[:count]
    # 边界扫描只做一次：一次调用里多个批次共享同一份源码快照。
    open_at = open_owners_at_boundaries(project)
    packet_dir = control_dir(project) / DISPATCH_DIR
    packet_dir.mkdir(parents=True, exist_ok=True)

    for chosen in chosen_keys:
        batch = Batch(chosen, batches[chosen]["start"], batches[chosen]["end"])
        packet_path = packet_dir / f"{chosen}.md"
        packet_path.write_text(
            task_packet(project, batch, open_at), encoding="utf-8", newline="\n"
        )
        batches[chosen]["status"] = "dispatched"
        print(f"已派发 {chosen}；任务包: {packet_path.relative_to(project).as_posix()}")

    save_state(project, state)
    if len(chosen_keys) == 1:
        return 0
    remaining = len(pending) - len(chosen_keys)
    suffix = f"，剩余 {remaining} 个待派发" if remaining else ""
    print(f"本次共派发 {len(chosen_keys)} 个批次{suffix}。")
    return 0


def check_batch(project: Path, batch: Batch) -> list[str]:
    """Return problems for one batch; empty means it passed."""
    problems: list[str] = []
    pages_dir = project / "latex" / "pages"
    for identifier in batch.pages:
        path = pages_dir / f"{identifier}.tex"
        if not path.is_file():
            problems.append(f"缺文件: latex/pages/{identifier}.tex")
            continue
        text = path.read_text(encoding="utf-8")
        if "Generated page stub" in text:
            problems.append(f"仍是占位骨架: {identifier}")
        if not any(
            line.strip().startswith("% Source page:") for line in text.splitlines()
        ):
            problems.append(f"缺来源页标记: {identifier}")
    if problems:
        return problems

    from semantics.sources import audit_project

    try:
        config, _ = load_config(project)
        _, issues = audit_project(project, config)
    except ConfigurationError as exc:
        return [f"语义审计配置错误: {exc}"]
    wanted = {
        f"latex/pages/{identifier}.tex" for identifier in batch.pages
    }
    for issue in issues:
        if issue.path in wanted:
            problems.append(f"{issue.path}:{issue.line}: {issue.code}: {issue.message}")
    return problems


def cmd_verify(project: Path, target: str) -> int:
    state = load_state(project)
    batches = state.get("batches") or {}
    matches = [key for key in batches if key == target]
    if not matches:
        print(f"未知批次: {target}", file=sys.stderr)
        return 2
    chosen = matches[0]
    batch = Batch(chosen, batches[chosen]["start"], batches[chosen]["end"])
    problems = check_batch(project, batch)
    if problems:
        batches[chosen]["status"] = "in_progress"
        save_state(project, state)
        for problem in problems:
            print(f"  - {problem}")
        print(f"{chosen} 未通过（{len(problems)} 项）。")
        return 1
    batches[chosen]["status"] = "verified"
    save_state(project, state)
    print(f"{chosen} 通过。")
    return 0


def cmd_status(project: Path) -> int:
    state = load_state(project)
    batches = state.get("batches") or {}
    if not batches:
        print("尚未规划批次。")
        return 0
    order = sorted(batches, key=lambda key: batches[key]["start"])
    counts: dict[str, int] = {}
    for key in order:
        status = batches[key]["status"]
        counts[status] = counts.get(status, 0) + 1
        print(
            f"{key}  pages-{batches[key]['start']:03d}..{batches[key]['end']:03d}  {status}"
        )
    summary = "，".join(f"{name} {value} 批" for name, value in sorted(counts.items()))
    print(f"共 {len(order)} 批：{summary}")
    return 0


def git(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def cmd_checkpoint(project: Path, target: str, message: str, dry_run: bool) -> int:
    """Commit one verified batch as a checkpoint.

    Only the dispatcher commits, and only after the batch passed verification.
    Paths are staged explicitly (never ``git add -A``) so an unrelated change
    can never ride along.
    """
    state = load_state(project)
    batches = state.get("batches") or {}
    if target not in batches:
        print(f"未知批次: {target}", file=sys.stderr)
        return 2

    # 提交必须建立在一次通过的验收之上：先 verify 再 checkpoint。
    status = batches[target].get("status")
    if status not in {"verified", "committed"}:
        print(
            f"{target} 尚未通过验收（当前状态 {status}）；"
            f"先运行 verify {target}。",
            file=sys.stderr,
        )
        return 1

    if git(project, "rev-parse", "--show-toplevel").returncode != 0:
        print(f"项目不是 Git 工作树: {project}", file=sys.stderr)
        return 2

    problems = check_batch(project, Batch(target, batches[target]["start"], batches[target]["end"]))
    if problems:
        for problem in problems:
            print(f"  - {problem}")
        print(f"{target} 未通过校验，拒绝提交检查点。", file=sys.stderr)
        return 1

    batch = Batch(target, batches[target]["start"], batches[target]["end"])
    paths = [f"latex/pages/{identifier}.tex" for identifier in batch.pages]
    missing = [path for path in paths if not (project / path).is_file()]
    if missing:
        for path in missing:
            print(f"  - 缺文件: {path}", file=sys.stderr)
        return 1
    staged = git(project, "add", "--", *paths)
    if staged.returncode != 0:
        print(staged.stderr.strip(), file=sys.stderr)
        return 2

    if not message:
        message = f"<agent><content> transcribe pages {batch.start:03d}-{batch.end:03d}"
    if dry_run:
        diff = git(project, "diff", "--cached", "--stat")
        if not diff.stdout.strip():
            print(f"[dry-run] {target} 没有需要提交的改动。")
            return 0
        print(f"[dry-run] 将提交 {len(paths)} 个文件：{message}")
        print(diff.stdout.strip())
        return 0

    staged_diff = git(project, "diff", "--cached", "--quiet")
    if staged_diff.returncode == 0:
        print(f"{target} 没有需要提交的改动（工作树已与该批一致）。", file=sys.stderr)
        return 0

    committed = git(project, "commit", "-m", message)
    if committed.returncode != 0:
        print(f"{target} 提交失败：", file=sys.stderr)
        print(committed.stderr.strip() or committed.stdout.strip(), file=sys.stderr)
        return 2
    batches[target]["status"] = "committed"
    batches[target]["checkpoint"] = git(
        project, "rev-parse", "--short", "HEAD"
    ).stdout.strip()
    save_state(project, state)
    print(f"{target} 已提交检查点 {batches[target]['checkpoint']}：{message}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="调度者：规划批次、生成单元任务包、校验批次产出。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="按连续页规划批次")
    plan.add_argument("--batch", type=int, default=10, help="每批页数（默认 10）")
    plan.add_argument(
        "--concurrency",
        type=int,
        default=0,
        help=(
            "软上限：允许同时在跑的批次数。0（默认）= 不设上限，"
            "由运行环境决定实际并发；传正整数才启用排队门"
        ),
    )
    nxt = sub.add_parser("next", help="派发待处理批次并生成任务包")
    nxt.add_argument(
        "--count",
        type=int,
        default=1,
        help="本次派发几个批次；0 = 全部待处理（默认 1）",
    )
    nxt.add_argument(
        "--force", action="store_true", help="越过已配置的软上限（concurrency > 0 时才有意义）"
    )
    verify = sub.add_parser("verify", help="校验一个批次")
    verify.add_argument("batch", help="批次 ID，例如 b001-010")
    checkpoint = sub.add_parser("checkpoint", help="把已通过校验的批次提交为检查点")
    checkpoint.add_argument("batch", help="批次 ID，例如 b001-010")
    checkpoint.add_argument(
        "-m", "--message", default="", help="提交消息；缺省用规范格式自动生成"
    )
    checkpoint.add_argument(
        "--dry-run", action="store_true", help="只显示将提交的内容，不真正提交"
    )
    sub.add_parser("status", help="列出所有批次状态")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        print(f"项目目录不存在: {project}", file=sys.stderr)
        return 2
    try:
        if args.command == "plan":
            if args.batch < 1:
                print("--batch 必须为正整数。", file=sys.stderr)
                return 2
            if args.concurrency < 0:
                print("--concurrency 不能为负数（0 表示不设上限）。", file=sys.stderr)
                return 2
            return cmd_plan(project, args.batch, args.concurrency)
        if args.command == "next":
            if args.count < 0:
                print("--count 不能为负数（0 表示全部）。", file=sys.stderr)
                return 2
            return cmd_next(project, args.count, args.force)
        if args.command == "verify":
            return cmd_verify(project, args.batch)
        if args.command == "checkpoint":
            return cmd_checkpoint(project, args.batch, args.message, args.dry_run)
        if args.command == "status":
            return cmd_status(project)
    except ConfigurationError as exc:
        print(f"语义审计配置错误: {exc}", file=sys.stderr)
        return 2
    print(f"未知命令: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
