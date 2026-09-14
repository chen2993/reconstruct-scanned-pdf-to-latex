#!/usr/bin/env python3
"""把本仓库作为技能挂到本机的 Codex 与 Claude Code 技能目录。

开发期用目录联接（junction）而不是复制：改仓库即是改技能，两个运行环境
立刻看到同一份内容，避免“复制过去的那份”和仓库漂移。

用法::

    python -X utf8 scripts/deploy_skill.py            # 部署/刷新
    python -X utf8 scripts/deploy_skill.py --status    # 只查看现状
    python -X utf8 scripts/deploy_skill.py --remove     # 移除部署
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "reconstruct-scanned-pdf-to-latex"
REPO = Path(__file__).resolve().parent.parent

def home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())

def junk_when_linked() -> tuple[str, ...]:
    return (".git", "tests", "tmp", "__pycache__", ".pytest_cache", ".ruff_cache")

def targets(shared: Path | None) -> list[tuple[str, Path]]:
    base = home()
    codex = Path(os.environ.get("CODEX_HOME") or base / ".codex") / "skills" / SKILL_NAME
    claude = base / ".claude" / "skills" / SKILL_NAME
    result = [("Codex", codex), ("Claude Code", claude)]
    if shared is not None:
        result.append(("共享层", shared))
    return result

def link_state(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return "缺失"
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return f"链接 -> {os.path.realpath(path)}"
    if path.is_dir():
        return "实体目录"
    return "非目录"

def create_junction(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        raise RuntimeError(f"目标已存在，请先移除: {link}")
    # 目录联接不需要管理员权限，且对两个运行环境都透明。
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"创建目录联接失败: {link}\n{result.stdout}{result.stderr}"
        )

def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        # 只删除联接本身，绝不递归进入目标目录。
        path.rmdir()
        return
    raise RuntimeError(f"拒绝删除实体目录，请人工确认: {path}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把本仓库部署为本机技能。")
    parser.add_argument("--status", action="store_true", help="只打印当前部署状态")
    parser.add_argument("--remove", action="store_true", help="移除已部署的联接")
    parser.add_argument(
        "--shared",
        type=Path,
        help="可选的共享层目录（例如 .agents/skills 下的同名联接）",
    )
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    entries = targets(args.shared)

    if args.status:
        for label, path in entries:
            print(f"{label:12s} {path}\n              {link_state(path)}")
        return 0

    if args.remove:
        for label, path in entries:
            try:
                remove_path(path)
                print(f"{label:12s} 已移除")
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        return 0

    if not (REPO / "SKILL.md").is_file():
        print(f"仓库缺少 SKILL.md: {REPO}", file=sys.stderr)
        return 2

    failures = 0
    for label, path in entries:
        state = link_state(path)
        if state.startswith("链接"):
            print(f"{label:12s} 已是链接，跳过: {path}")
            continue
        if state == "实体目录":
            print(
                f"{label:12s} 已存在实体目录，未覆盖；请确认后手工处理: {path}",
                file=sys.stderr,
            )
            failures += 1
            continue
        if state == "非目录":
            print(f"{label:12s} 位置被非目录占用: {path}", file=sys.stderr)
            failures += 1
            continue
        try:
            create_junction(path, REPO)
            print(f"{label:12s} 已部署: {path} -> {REPO}")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            failures += 1

    print(
        "\n技能目录内不会带 "
        + "、".join(junk_when_linked())
        + " 的语义：它们只存在于本仓库，加载技能时不参与。"
    )
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
