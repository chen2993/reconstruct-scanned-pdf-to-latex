"""变异测试：临时注入缺陷，确认契约测试真的会失败。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLASS = REPO / "template" / "base.cls"
BS = "\\"

MUTATIONS = {
    # 恢复“做题本隐藏前后置”的旧行为
    "workbook_hides_matter": (
        BS + "newcommand{" + BS + "book@mode@workbook}{%\n"
        "  " + BS + "book@showstructuretrue\n"
        "  " + BS + "book@showmattertrue\n"
        "  " + BS + "book@showmediatrue\n"
        "  " + BS + "book@workbooktrue\n"
        "}",
        BS + "newcommand{" + BS + "book@mode@workbook}{%\n"
        "  " + BS + "book@showstructuretrue\n"
        "  " + BS + "book@workbooktrue\n"
        "}",
    ),
    # 恢复“选项在 document 开始后才应用”的旧行为，纸型会被静默忽略
    "late_option_application": (
        BS + "AtEndPreamble{" + BS + "book@applyinitialoptions}",
        BS + "AtBeginDocument{" + BS + "book@applyinitialoptions}",
    ),
    # 原书尺寸只记录不应用：original profile 会悄悄退回默认纸张
    "original_size_not_applied": (
        "  " + BS + "book@originalsizeappliedtrue\n"
        "  " + BS + "geometry{paperwidth=" + BS + "book@originalwidth,paperheight="
        + BS + "book@originalheight,margin=15mm}%",
        "  " + BS + "book@originalsizeappliedtrue",
    ),
    # 删掉缺尺寸的显式报错：缺尺寸时静默沿用引擎默认纸张
    "missing_size_check_removed": (
        BS + "AtBeginDocument{%\n"
        "  " + BS + "ifbook@originalsizeapplied" + BS + "else\n"
        "    " + BS + "ClassError{base}{Original paper size is not configured}%\n"
        "      {Call " + BS + "string" + BS + "booksetoriginalpagesize{width}{height} from the project class preamble.}%\n"
        "  " + BS + "fi\n}",
        "",
    ),
    # 答案在所有目标都可见：做题本泄漏答案
    "answers_never_hidden": (
        BS + "newcommand{" + BS + "book@selectanswer}{%\n"
        "  " + BS + "book@selectedanswerfalse\n",
        BS + "newcommand{" + BS + "book@selectanswer}{%\n"
        "  " + BS + "book@selectedanswertrue\n",
    ),
}


def main() -> int:
    raw = CLASS.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    # 变异锚点统一用 \n 书写；写回时恢复原文件的换行风格。
    original = raw.decode("utf-8").replace("\r\n", "\n")
    failures = 0
    try:
        for name, (before, after) in MUTATIONS.items():
            if before not in original:
                print(f"[跳过] {name}: 找不到锚点")
                failures += 1
                continue
            CLASS.write_text(
                original.replace(before, after, 1).replace("\n", newline),
                encoding="utf-8",
                newline="",
            )
            result = subprocess.run(
                [sys.executable, "-X", "utf8", "-m", "pytest", "tests/test_class_contract.py", "-q", "--no-header", "-x"],
                capture_output=True, text=True, encoding="utf-8", cwd=REPO,
            )
            caught = result.returncode != 0
            print(f"[{'捕获' if caught else '漏过'}] {name}")
            if not caught:
                failures += 1
            else:
                tail = [line for line in result.stdout.splitlines() if line.startswith(("FAILED", "E "))]
                for line in tail[:3]:
                    print("      " + line[:160])
    finally:
        CLASS.write_bytes(raw)
    print("变异测试完成；未捕获数 =", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
