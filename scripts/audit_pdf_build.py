"""成品 PDF 的对象级审计：位图包装、答案泄漏与纸型一致性。

只读取 PDF 对象树、页面几何和文本层，不把它们当作正文来源。重建产物的文本层
由 LaTeX 直接生成，因此这里的文本读取只用于**校验**，不用于转写。

两类硬失败：

* **整页位图**：某页可见面积被单张位图覆盖到阈值以上，说明这一页是截图包装而
  不是重新排版的 LaTeX。原书扫描图不得出现在成品里。
* **答案泄漏**：做题本里出现了本该隐藏的答案哨兵文本。答案文字的位置和长度
  无法靠目视抽查保证，只能在构建时用哨兵比对。

纸型集合与空文字页只报告不判错：扉页、章首页和篇章页本来就稀疏，混合纸型也
可能是有意的设计，但它们必须出现在构建记录里才能被人复核。

用法::

    python -X utf8 scripts/audit_pdf_build.py build.pdf
    python -X utf8 scripts/audit_pdf_build.py workbook.pdf --sentinels sentinels.txt
    python -X utf8 scripts/audit_pdf_build.py build.pdf --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_profiles import (  # noqa: E402
    POINTS_PER_MM,
    ProfileError,
    expected_mm,
    within_tolerance,
)
from pdf_backend import require_pymupdf  # noqa: E402

# 单页被单张位图覆盖到该比例以上即视为整页图片包装。
FULL_PAGE_RASTER_RATIO = 0.6

# LaTeX 会在中西文边界插入空格，也会把长行折成多行，因此哨兵比对必须先去掉
# 全部空白。否则“答案就在这一页”会因为一个空格而判为通过。
WHITESPACE = re.compile(r"\s+")

def normalize(text: str) -> str:
    return WHITESPACE.sub("", text)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检查成品 PDF 是否含整页位图或泄漏的答案哨兵。"
    )
    parser.add_argument("pdf", type=Path, help="待检查的成品 PDF")
    parser.add_argument(
        "--sentinels",
        type=Path,
        help="答案哨兵文本文件；每行一条，命中即失败",
    )
    parser.add_argument(
        "--raster-ratio",
        type=float,
        default=FULL_PAGE_RASTER_RATIO,
        help=f"判定整页位图的覆盖比例阈值（默认 {FULL_PAGE_RASTER_RATIO}）",
    )
    parser.add_argument(
        "--profile",
        help=(
            "按该目标的纸型核对每页 MediaBox（a4/pad11/pad13，或项目已登记的尺寸名）；"
            "省略时不核对尺寸，只报告实际纸型集合"
        ),
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    return parser.parse_args()

def read_sentinels(path: Path | None) -> list[str]:
    if path is None:
        return []
    if not path.is_file():
        raise RuntimeError(f"哨兵文件不存在: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        normalize(line)
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]

def page_raster_ratio(page: object) -> float:
    """Largest fraction of the page area covered by one raster image."""

    page_area = abs(page.rect.width * page.rect.height)
    if page_area <= 0:
        return 0.0
    largest = 0.0
    for info in page.get_image_info():
        bbox = info.get("bbox")
        if not isinstance(bbox, tuple) or len(bbox) != 4:
            continue
        left, top, right, bottom = (float(value) for value in bbox)
        largest = max(largest, abs((right - left) * (bottom - top)) / page_area)
    return largest

def inspect(document: object, sentinels: list[str], raster_ratio: float) -> dict:
    report: dict = {
        "pages": document.page_count,
        "media_boxes": [],
        "page_sizes": [],
        "full_page_rasters": [],
        "blank_text_pages": [],
        "sentinel_hits": [],
    }
    if sentinels:
        report["sentinel_terms"] = len(sentinels)
    for index in range(document.page_count):
        page = document.load_page(index)
        box = (round(page.rect.width, 1), round(page.rect.height, 1))
        if box not in report["media_boxes"]:
            report["media_boxes"].append(box)
        report["page_sizes"].append(box)
        ratio = page_raster_ratio(page)
        if ratio >= raster_ratio:
            report["full_page_rasters"].append(
                {"page": index + 1, "coverage": round(ratio, 3)}
            )
        text = page.get_text()
        if not text.strip():
            report["blank_text_pages"].append(index + 1)
        normalized = normalize(text)
        for term in sentinels:
            if term in normalized:
                report["sentinel_hits"].append({"page": index + 1, "term": term})
    return report

def main() -> int:
    args = parse_args()
    pdf = args.pdf.resolve()
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        print(f"PDF 不存在或扩展名无效: {pdf}", file=sys.stderr)
        return 2
    try:
        sentinels = read_sentinels(args.sentinels)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    fitz = require_pymupdf()

    try:
        with fitz.open(pdf) as document:
            report = inspect(document, sentinels, args.raster_ratio)
    except Exception as exc:  # PyMuPDF exposes several document-specific errors.
        print(f"无法读取 PDF: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    failures: list[str] = []
    profile_note = ""
    if args.profile:
        try:
            want_width, want_height = expected_mm(args.profile, pdf.parent)
        except ProfileError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        # 逐页核对而不是只看集合：同一目标里混进别的纸型，只看"集合里有正确的那个"
        # 会漏掉真正错的那几页。
        page_sizes = report.get("page_sizes") or []
        wrong = [
            (index, size)
            for index, size in enumerate(page_sizes, 1)
            if not within_tolerance(
                (size[0] / POINTS_PER_MM, size[1] / POINTS_PER_MM),
                (want_width, want_height),
            )
        ]
        profile_note = (
            f"{args.profile} 期望 {want_width:.1f}×{want_height:.1f}mm"
        )
        for index, size in wrong:
            failures.append(
                f"第 {index} 页纸型不符：{size[0] / POINTS_PER_MM:.2f}×"
                f"{size[1] / POINTS_PER_MM:.2f}mm，"
                f"期望 {want_width:.2f}×{want_height:.2f}mm"
            )

    for item in report["full_page_rasters"]:
        failures.append(
            f"第 {item['page']} 页被整页位图覆盖 {item['coverage']:.0%}；"
            "重建产物不得用扫描图包装内容"
        )
    for item in report["sentinel_hits"]:
        failures.append(
            f"第 {item['page']} 页出现应隐藏的答案哨兵: {item['term']!r}"
        )

    if args.json:
        payload = dict(report)
        payload["ok"] = not failures
        payload["failures"] = failures
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if failures else 0

    boxes = "、".join(f"{width}×{height}pt" for width, height in report["media_boxes"])
    profile_suffix = f"；核对 {profile_note}" if profile_note else ""
    print(f"页数 {report['pages']}；纸型集合 {boxes}{profile_suffix}")
    if len(report["media_boxes"]) > 1:
        print("提示：本目标存在多种纸型，请确认这是设计意图而不是漏设的 profile。")
    if report["blank_text_pages"]:
        print(
            "提示：以下页没有文本层，确认它们确实是无文字的扉页或整页图："
            + "、".join(str(page) for page in report["blank_text_pages"])
        )
    if report["full_page_rasters"]:
        print(f"整页位图 {len(report['full_page_rasters'])} 页。")
    if sentinels and not report["sentinel_hits"]:
        print(f"答案哨兵检查通过：{len(sentinels)} 条均未出现。")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        print(f"成品审计未通过：{len(failures)} 个问题")
        return 1
    print("成品审计通过。")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
