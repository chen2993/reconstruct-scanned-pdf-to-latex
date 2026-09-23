#!/usr/bin/env python3
"""每页读图预算：由 ``crop_page.py`` 强制执行，本文件提供账本与只读报告。

为什么需要它
------------
逐页转写最容易失败的时机不是"看不清"，而是**看太多**：实测有单元为了"更仔细"
把一页裁成 20 多张图逐张读，上下文烧光、任务中途崩溃，前面读的全白费。所以预算
是任务成败的硬边界，而且必须**由脚本强制**——靠模型自觉记录是不可靠的。

计数点在 ``crop_page.py``：**裁剪一张图就是一次读图**，不需要单元额外申报。
因此额度用完时裁图会直接失败，而不是"读的时候才发现"，这给单元留出了反应时间。

排除项（不占预算）：``--overview`` 总览。总览是定位手段，鼓励用；它本身不读内容。

用法::

    python -X utf8 scripts/read_budget.py <project> check pages-013
    python -X utf8 scripts/read_budget.py <project> report
    python -X utf8 scripts/read_budget.py <project> spend pages-013 tmp/x.png   # 手工补记
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from page_workspace import control_dir  # noqa: E402

LEDGER_FILE = "read-budget.json"

# 每页默认读图预算。含单元自己的探针图；4 条横带 + 1–2 张收窄补充刚好够用。
# 这是硬上限：超预算不是"更仔细"，是任务失败。
DEFAULT_LIMIT = 6


class BudgetError(RuntimeError):
    """预算已用尽或账本不可用；调用方应停下来报告，而不是继续读图。"""


class UsageError(RuntimeError):
    """输入不符合契约；退出码与其它脚本一致为 2。"""


def ledger_path(project: Path) -> Path:
    return control_dir(project) / LEDGER_FILE


def load(project: Path) -> dict:
    path = ledger_path(project)
    if not path.is_file():
        return {"limit": DEFAULT_LIMIT, "pages": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BudgetError(f"无法读取读图账本 {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BudgetError("读图账本顶层必须是对象")
    payload.setdefault("limit", DEFAULT_LIMIT)
    payload.setdefault("pages", {})
    return payload


def save(project: Path, payload: dict) -> None:
    path = ledger_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def used(project: Path, page: str) -> int:
    entry = load(project)["pages"].get(page) or {}
    return int(entry.get("count", 0))


def describe(project: Path, page: str) -> str:
    payload = load(project)
    limit = int(payload["limit"])
    entry = payload["pages"].get(page)
    if entry is None:
        return f"{page} 尚未读图（预算 {limit} 次；--overview 总览不计入）"
    count = int(entry.get("count", 0))
    lines = [
        f"{page} 已读 {count}/{limit} 次，剩余 {max(0, limit - count)} 次"
        "（--overview 总览不计入）"
    ]
    images = entry.get("images") or []
    seen: dict[str, int] = {}
    for image in images:
        seen[image] = seen.get(image, 0) + 1
    for image in images:
        lines.append(f"  {image}" + ("  <-- 重复登记" if seen[image] > 1 else ""))
    if count >= limit:
        lines.append("注意: 预算已用尽；请停下报告，不要继续裁图。")
    return "\n".join(lines)


def charge_read(project: Path, page: str, image: Path) -> None:
    """登记一次读图；超预算抛 ``BudgetError``。

    由 ``crop_page.py`` 在成功产出裁图后调用。同一张图重复裁剪（例如换了输出
    路径但内容相同）仍计一次开销，因为单元确实又读了一遍。
    """
    payload = load(project)
    limit = int(payload["limit"])
    entry = payload["pages"].setdefault(page, {"count": 0, "images": []})
    count = int(entry.get("count", 0))
    if count >= limit:
        raise BudgetError(
            f"{page} 的读图预算已用尽（{count}/{limit}）。\n"
            "超预算不是更仔细，而是任务失败：请停下来用 BLOCKED 报告卡在哪一块，"
            "不要继续裁图。确需更多额度时由调度者显式提高上限。"
        )
    entry["count"] = count + 1
    entry.setdefault("images", []).append(str(image))
    save(project, payload)
    remaining = limit - entry["count"]
    print(f"读图预算 {entry['count']}/{limit}（本页剩余 {remaining} 次；--overview 不计入）")
    if remaining == 0:
        print(
            "注意: 这是本页最后一次预算，再裁图会被拒绝。",
            file=sys.stderr,
        )


def set_limit(project: Path, page: str, limit: int) -> None:
    """由调度者显式提高某页上限。"""
    if limit < 1:
        raise UsageError("--reset-budget 必须是正整数")
    payload = load(project)
    payload["limit"] = limit
    entry = payload["pages"].setdefault(page, {"count": 0, "images": []})
    save(project, payload)
    print(f"{page} 读图预算上限已设为 {limit}（已用 {int(entry.get('count', 0))} 次）")


def cmd_check(project: Path, page: str) -> int:
    print(describe(project, page))
    payload = load(project)
    entry = payload["pages"].get(page) or {}
    return 1 if int(entry.get("count", 0)) >= int(payload["limit"]) else 0


def cmd_report(project: Path) -> int:
    payload = load(project)
    limit = int(payload["limit"])
    pages = payload["pages"]
    if not pages:
        print(f"尚未登记任何读图（预算 {limit} 次/页）。")
        return 0
    total = sum(int(entry.get("count", 0)) for entry in pages.values())
    exhausted = sorted(
        page for page, entry in pages.items() if int(entry.get("count", 0)) >= limit
    )
    partial = sorted(
        (page, int(entry.get("count", 0)))
        for page, entry in pages.items()
        if 0 < int(entry.get("count", 0)) < limit
    )
    print(f"读图预算 {limit} 次/页；已登记 {len(pages)} 页，共 {total} 次。")
    if partial:
        print("\n尚有余量：")
        for page, count in partial:
            print(f"  {page}  {count}/{limit}")
    if exhausted:
        print("\n已用尽：")
        for page in exhausted:
            print(f"  {page}  {int(pages[page].get('count', 0))}/{limit}")
        print(
            "\n已用尽的页对应单元应停下报告；确需更多额度由调度者显式提高上限。",
            file=sys.stderr,
        )
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="每页读图预算的账本与只读报告。")
    parser.add_argument("project", type=Path, help="重建项目根目录")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="查看某页余额与已读清单")
    check.add_argument("page")
    sub.add_parser("report", help="查看全部页的读图状态")
    spend = sub.add_parser("spend", help="手工补记一次读图（正常由 crop_page.py 自动登记）")
    spend.add_argument("page")
    spend.add_argument("image", nargs="?", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        print(f"项目目录不存在: {project}", file=sys.stderr)
        return 2
    try:
        if args.command == "check":
            return cmd_check(project, args.page)
        if args.command == "report":
            return cmd_report(project)
        charge_read(project, args.page, Path(args.image or "<manual>"))
        return 0
    except (UsageError, BudgetError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
