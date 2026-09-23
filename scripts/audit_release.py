#!/usr/bin/env python3
"""发布前泄漏审计：确认原书扫描与页图没有进入版本控制。

为什么它必须由脚本做
--------------------
原书扫描件和页图是**本地 QA 输入**，不是项目源码。它们一旦被提交，即使事后删除
仍能从 Git 历史恢复——那就是既成事实的再分发。人工核对几十条路径容易漏，所以
发布前的这一步必须可重复、可核对。

本脚本只**报告**，不自行删除：历史问题（已经提交过的扫描件）需要人工决定是改写
历史、还是另起仓库，属于破坏性操作。

用法::

    python -X utf8 scripts/audit_release.py <project>
    python -X utf8 scripts/audit_release.py <project> --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 图片与 PDF 形式的页图/扫描：出现在版本控制里即为泄漏。
SCAN_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pdf")

# 本地 QA 输入目录：其内容一律不该被跟踪。
#
# 注意 `references` 有歧义：在**重建项目**里它是存放原书扫描与外部参考的 QA 输入
# 目录；但在**技能仓库**里 `references/` 是技能自己的文档目录，必须被跟踪。
# 因此只有在它不呈现"技能文档"特征时才按 QA 输入处理。
LOCAL_INPUT_DIRS = ("reference", "references", "sources")


def looks_like_skill_repository(project: Path) -> bool:
    """判断这是技能仓库（文档目录正当）还是重建项目（references 是 QA 输入）。

    判据取"同时具备技能结构特征"：根目录有 SKILL.md，且 references 下是成体系的
    文档而不是原书资料。任一不满足就按重建项目处理，保持原有的严格检查。
    """

    if not (project / "SKILL.md").is_file():
        return False
    references = project / "references"
    if not references.is_dir():
        return False
    # 技能文档目录的特征：有多篇 .md，且没有图片/PDF 直接躺在下面。
    markdown = list(references.rglob("*.md"))
    if len(markdown) < 3:
        return False
    stray_assets = [
        item
        for item in references.rglob("*")
        if item.is_file() and item.suffix.lower() in SCAN_SUFFIXES
    ]
    return not stray_assets

# 仓库级法律文件：源码包与发布包缺任一都不合格。
REQUIRED_FILES = ("LICENSE", "NOTICE.md")

# .gitignore 必须覆盖的路径；缺一项就意味着下一次提交可能把扫描件带进去。
#
# `/references/` 只在重建项目里必需（那是 QA 输入目录）；技能仓库把它用作文档
# 目录，必须被跟踪，因此不能要求忽略它。`required_ignores()` 按类型给出清单。
REQUIRED_IGNORES = (
    "/reference/",
    "/references/",
    "/sources/",
    "/dist/",
    "/tmp/",
)
SKILL_REQUIRED_IGNORES = (
    "/reference/",
    "/sources/",
    "/dist/",
    "/tmp/",
)


def required_ignores(project: Path) -> tuple[str, ...]:
    """按仓库类型给出必需的忽略项。

    重建项目要挡 `references/`（原书扫描与外部参考）；技能仓库的 `references/`
    是文档目录，反过来必须能提交。
    """

    return (
        SKILL_REQUIRED_IGNORES
        if looks_like_skill_repository(project)
        else REQUIRED_IGNORES
    )


def git(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def tracked_files(project: Path) -> list[str]:
    result = git(project, "ls-files")
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def history_scan_hits(project: Path) -> list[str]:
    """曾经提交过的扫描/页图——即使当前已删除，历史里仍可恢复。"""

    result = git(project, "log", "--all", "--pretty=format:", "--name-only")
    if result.returncode != 0:
        return []
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        name = line.strip()
        if name and name.lower().endswith(SCAN_SUFFIXES):
            seen.add(name)
    return sorted(seen)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="发布前检查：扫描件/页图是否进入版本控制，法律文件是否齐备。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        print(f"项目目录不存在: {project}", file=sys.stderr)
        return 2

    if git(project, "rev-parse", "--show-toplevel").returncode != 0:
        print(f"项目不是 Git 工作树: {project}", file=sys.stderr)
        return 2

    tracked = tracked_files(project)
    tracked_scans = sorted(
        name for name in tracked if name.lower().endswith(SCAN_SUFFIXES)
    )
    local_input_dirs = LOCAL_INPUT_DIRS
    if looks_like_skill_repository(project):
        # 技能仓库：references/ 是文档目录，只有 reference/ 与 sources/ 仍是 QA 输入。
        local_input_dirs = tuple(
            directory for directory in LOCAL_INPUT_DIRS if directory != "references"
        )
    tracked_local = sorted(
        name
        for name in tracked
        if any(
            name == directory or name.startswith(directory + "/")
            for directory in local_input_dirs
        )
    )
    historical = history_scan_hits(project)

    ignore_path = project / ".gitignore"
    ignore_text = ignore_path.read_text(encoding="utf-8") if ignore_path.is_file() else ""
    missing_ignores = [
        entry for entry in required_ignores(project) if entry not in ignore_text
    ]
    missing_files = [
        name for name in REQUIRED_FILES if not (project / name).is_file()
    ]

    problems: list[str] = []
    if tracked_scans:
        problems.append(
            f"版本控制里跟踪着 {len(tracked_scans)} 个图片/PDF 文件，"
            "其中可能有原书扫描或页图"
        )
    if tracked_local:
        problems.append(
            f"版本控制里跟踪着本地 QA 输入目录下的 {len(tracked_local)} 个文件"
        )
    if missing_ignores:
        problems.append(".gitignore 未覆盖必需路径: " + "、".join(missing_ignores))
    if missing_files:
        problems.append("缺少仓库级法律文件: " + "、".join(missing_files))

    payload = {
        "project": str(project),
        "tracked_files": len(tracked),
        "tracked_scans": tracked_scans,
        "tracked_local_inputs": tracked_local,
        "historical_scans": historical,
        "missing_ignores": missing_ignores,
        "missing_files": missing_files,
        "problems": problems,
        "ok": not problems,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if problems else 0

    kind = "技能仓库（references/ 视为文档目录）" if looks_like_skill_repository(project) else "重建项目"
    print(f"已跟踪文件 {len(tracked)} 个；按「{kind}」检查。")
    if tracked_scans:
        print(f"\n被跟踪的图片/PDF（{len(tracked_scans)} 个）：", file=sys.stderr)
        for name in tracked_scans[:40]:
            print(f"  {name}", file=sys.stderr)
        if len(tracked_scans) > 40:
            print(f"  ...另有 {len(tracked_scans) - 40} 个", file=sys.stderr)
    if tracked_local:
        print(f"\n被跟踪的本地输入（{len(tracked_local)} 个）：", file=sys.stderr)
        for name in tracked_local[:20]:
            print(f"  {name}", file=sys.stderr)
    if historical:
        print(
            f"\n历史中曾出现过的图片/PDF（{len(historical)} 个）："
            "即使当前已删除，仍可从历史恢复。",
            file=sys.stderr,
        )
        for name in historical[:20]:
            print(f"  {name}", file=sys.stderr)
        print(
            "如需彻底移除，只能改写历史（破坏性操作）或另起新仓库；"
            "该决定由人工做出，本脚本不代做。",
            file=sys.stderr,
        )

    if problems:
        print()
        for problem in problems:
            print(f"问题: {problem}", file=sys.stderr)
        print(f"\n发布前审计未通过：{len(problems)} 个问题。", file=sys.stderr)
        return 1

    print("发布前审计通过：无扫描/页图进入版本控制，法律文件齐备。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
