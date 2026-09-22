#!/usr/bin/env python3
"""把本仓库作为技能部署到本机 AI 编码工具的技能目录。

开发期用目录联接（junction）而不是复制：改仓库即改技能，所有运行环境立刻看到
同一份内容，不会出现"某个工具里的那份"和仓库漂移。对已经用复制方式安装的旧
副本，本工具会指出它已过期，并在 `--force` 时替换成联接。

默认只部署到 4 个主用运行时：Codex、Claude Code、DSH、Kimi Code。本机还装了
其它携带技能目录的工具，它们不在默认范围内；需要时用 `--all` 或 `--only` 显式
指定，避免把同一份技能散落到一堆不用的目录里。

用法::

    python -X utf8 tools/deploy_skill.py --status          # 查看现状
    python -X utf8 tools/deploy_skill.py                   # 部署到 4 个主用运行时
    python -X utf8 tools/deploy_skill.py --force           # 归档过期实体副本并改为联接
    python -X utf8 tools/deploy_skill.py --all             # 连同其它已安装运行时
    python -X utf8 tools/deploy_skill.py --only codex,kimi # 只处理指定运行时
    python -X utf8 tools/deploy_skill.py --remove --only gemini
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_NAME = Path(__file__).resolve().parent.parent.name
REPO = Path(__file__).resolve().parent.parent

# 默认部署目标。这四个是实际在用的运行时，其余工具目录按需再开。
PRIMARY_RUNTIMES = ("codex", "claude", "dsh", "kimi")


def home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def runtime_roots() -> list[tuple[str, Path, str]]:
    """(运行时名, 技能根目录, 备注) —— 只列出本机存在的目录。

    各工具的约定不同：有的放 ``skills/``，OpenCode 放 ``skill/``，Kimi 的插件
    技能走自己的目录。这里按各自约定登记，未安装的运行时自动跳过。

    只有工具本体存在、但技能根目录尚未创建时（用户级技能目录常见这种情况）仍
    会保留条目，由部署时补建；工具本体不存在才算未安装。
    """

    base = home()
    candidates = [
        ("codex", base / ".codex" / "skills", ""),
        ("claude", base / ".claude" / "skills", ""),
        ("dsh", base / ".dsh" / "skills", ""),
        # Kimi Code 的用户级技能目录是 ~/.kimi-code/skills/；它另外也读
        # .claude/skills 与 .codex/skills，所以不要塞进厂商插件目录（会被升级覆盖）。
        ("kimi", base / ".kimi-code" / "skills", ""),
        # 以下不参与默认部署，仅供 --all / --only 使用。
        ("agents", base / ".agents" / "skills", "共享层"),
        ("opencode", base / ".config" / "opencode" / "skills", ""),
        ("opencode-legacy", base / ".config" / "opencode" / "skill", "OpenCode 旧布局"),
        ("pi", base / ".pi" / "agent" / "skills", ""),
        ("reasonix", base / ".reasonix" / "skills", ""),
        ("zcode", base / ".zcode" / "skills", ""),
        ("codebuddy", base / ".codebuddy" / "skills", ""),
        ("codewhale", base / ".codewhale" / "skills", ""),
        ("trae", base / ".trae-cn" / "skills", ""),
        ("astrbot", base / ".astrbot" / "data" / "skills", ""),
        ("cc-switch", base / ".cc-switch" / "skills", ""),
        ("workbuddy", base / ".workbuddy" / "skills", ""),
        ("doubao", base / "Doubao" / "skills", ""),
        ("gemini", base / ".gemini" / "skills", ""),
    ]
    # 判据是"工具本体是否安装"，不是"技能目录是否已存在"：就绪的状态里，用户级
    # 技能目录常常还没建过。技能目录位于工具主目录之下，因此检查父级。
    ready: list[tuple[str, Path, str]] = []
    for name, root, note in candidates:
        tool_home = root.parent
        if root.is_dir() or tool_home.is_dir():
            ready.append((name, root, note))
    return ready


def is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def link_target(path: Path) -> Path | None:
    if not is_link(path):
        return None
    try:
        return Path(os.path.realpath(path))
    except OSError:
        return None


def normalize_newlines(text: str) -> str:
    """CRLF 与 LF 视为同一内容：换行风格不是技能是否过期的判据。"""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def same_content(path: Path) -> bool:
    """实体副本是否与仓库一致。

    比较的是文本内容而不是原始字节：把仓库复制到别处时，Windows 的换行转换会把
    LF 变成 CRLF，按字节比会把内容相同的副本误判成过期。脚本清单也必须一致，
    否则"文件都在但少了一个"的旧副本会被当成已部署而跳过。
    """

    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        return False
    try:
        if normalize_newlines(skill_md.read_text(encoding="utf-8")) != normalize_newlines(
            (REPO / "SKILL.md").read_text(encoding="utf-8")
        ):
            return False
    except (OSError, UnicodeDecodeError):
        return False
    ignored = {"__pycache__", ".pytest_cache", ".ruff_cache"}
    repo_scripts = {
        item.relative_to(REPO / "scripts").as_posix()
        for item in (REPO / "scripts").rglob("*.py")
        if not ignored & set(item.parts)
    }
    local_scripts = {
        item.relative_to(path / "scripts").as_posix()
        for item in (path / "scripts").rglob("*.py")
        if not ignored & set(item.parts)
    } if (path / "scripts").is_dir() else set()
    return repo_scripts == local_scripts


def describe(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return "缺失"
    target = link_target(path)
    if target is not None:
        if Path(os.path.realpath(target)) == Path(os.path.realpath(REPO)):
            return f"已联接 -> {target}"
        return f"联接到其它位置 -> {target}"
    if path.is_dir():
        return "实体副本（与仓库一致）" if same_content(path) else "实体副本（已过期）"
    return "被非目录占用"


def create_junction(link: Path, target: Path) -> None:
    if link.exists() or link.is_symlink():
        raise RuntimeError(f"目标已存在，请先移除: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    # 目录联接不需要管理员权限，且对各运行环境透明。
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"创建目录联接失败: {link}\n{result.stdout}{result.stderr}")


def remove_link(path: Path) -> None:
    """只删除联接本身；看到实体目录就停下来交给人工判断。"""

    if not path.exists() and not path.is_symlink():
        return
    if is_link(path):
        path.rmdir()
        return
    raise RuntimeError(f"拒绝删除实体目录（可能是别处安装的副本），请人工确认: {path}")


def archive_stale_copy(path: Path) -> Path:
    """把过期的实体副本移出技能目录归档，而不是原地改名或直接删除。

    原地改名不够：多数运行时会递归扫描技能目录下的 `**/SKILL.md`，改过名的旧
    副本仍会被当成第二个同名技能加载。因此必须移出扫描范围。
    """

    archive_root = home() / ".skill-archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = archive_root / f"{path.name}-{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = archive_root / f"{path.name}-{stamp}-{suffix}"
        suffix += 1
    shutil.move(str(path), str(candidate))
    return candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把本仓库部署为本机各 AI 编码工具的技能（目录联接）。"
    )
    parser.add_argument("--status", action="store_true", help="只打印各运行时的部署状态")
    parser.add_argument("--remove", action="store_true", help="移除已部署的联接")
    parser.add_argument(
        "--force",
        action="store_true",
        help="遇到过期的实体副本时归档旧副本并改为联接",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="连同 4 个主用运行时之外的已安装工具一起处理",
    )
    parser.add_argument("--only", help="只处理逗号分隔的运行时名，例如 codex,claude,dsh")
    parser.add_argument("--json", action="store_true", help="与 --status 配合输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = runtime_roots()
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        known = {name for name, _, _ in roots}
        unknown = wanted - known
        if unknown:
            print(
                f"未知或本机不存在的运行时: {sorted(unknown)}；可用: {sorted(known)}",
                file=sys.stderr,
            )
            return 2
        roots = [item for item in roots if item[0] in wanted]
    elif not args.all:
        roots = [item for item in roots if item[0] in PRIMARY_RUNTIMES]
    if not roots:
        print("没有发现任何已安装的技能目录。", file=sys.stderr)
        return 2

    if not (REPO / "SKILL.md").is_file():
        print(f"仓库缺少 SKILL.md: {REPO}", file=sys.stderr)
        return 2

    entries = [(name, root / SKILL_NAME, note) for name, root, note in roots]

    if args.status:
        lines = []
        for name, path, note in entries:
            state = describe(path)
            lines.append({"runtime": name, "path": str(path), "state": state, "note": note})
            label = f"{name}（{note}）" if note else name
            print(f"{label:26s} {path}\n{'':26s} {state}")
        if args.json:
            import json

            print(json.dumps(lines, ensure_ascii=False, indent=2))
        return 0

    if args.remove:
        failures = 0
        for name, path, _ in entries:
            try:
                remove_link(path)
                print(f"{name:26s} 已移除")
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                failures += 1
        return 1 if failures else 0

    failures = 0
    for name, path, note in entries:
        label = f"{name}（{note}）" if note else name
        state = describe(path)

        if state.startswith("已联接"):
            print(f"{label:26s} 已联接，跳过")
            continue
        if state.startswith("联接到其它位置"):
            print(f"{label:26s} 联接到其它位置，未改动: {path}", file=sys.stderr)
            failures += 1
            continue
        if state == "实体副本（与仓库一致）":
            print(f"{label:26s} 实体副本与仓库一致；建议改用联接以免下次漂移: {path}")
            continue
        if state == "实体副本（已过期）":
            if not args.force:
                print(
                    f"{label:26s} 实体副本已过期，未改动；加 --force 可归档旧副本并改为联接",
                    file=sys.stderr,
                )
                failures += 1
                continue
            archived = archive_stale_copy(path)
            try:
                create_junction(path, REPO)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                failures += 1
                continue
            print(f"{label:26s} 旧副本已归档到 {archived}，并改为联接")
            continue
        if state == "被非目录占用":
            print(f"{label:26s} 位置被非目录占用，未改动: {path}", file=sys.stderr)
            failures += 1
            continue

        try:
            create_junction(path, REPO)
            print(f"{label:26s} 已部署 -> {REPO}")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            failures += 1

    if failures:
        print(f"\n{failures} 个运行时未处理完成。", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
