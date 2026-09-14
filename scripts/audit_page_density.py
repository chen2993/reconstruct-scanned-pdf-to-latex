"""按页面墨迹密度筛查成品 PDF 的异常稀疏页。

重建版与原书页数不一致时，逐页翻看大量渲染图既慢又耗上下文。更有效的做法是
先用墨迹统计把可疑页缩小到少数几个候选，再只打开那几页做人工比对。

本脚本只做诊断，不判定对错：封面、篇章扉页、章首页本来就稀疏。它输出的是
"值得优先人工确认"的候选页，而不是错误列表，因此退出码始终为 0
（除无法读取 PDF 外）。

用法::

    python -X utf8 scripts/audit_page_density.py build.pdf
    python -X utf8 scripts/audit_page_density.py build.pdf --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_backend import require_pymupdf  # noqa: E402

pymupdf = require_pymupdf()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按墨迹密度筛查 PDF 的异常稀疏页；只渲染图像，不读取正文文字。"
    )
    parser.add_argument("pdf", type=Path, help="成品或中间 PDF")
    parser.add_argument(
        "--dpi", type=int, default=36, help="栅格化分辨率（默认 36，仅用于统计）"
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=0.5,
        help="低于全书墨迹中位数该比例的页面列为候选（默认 0.5）",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="最多列出多少张候选页（默认 25，按稀疏程度排序）",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    return parser.parse_args()


def ink_fraction(page, dpi: int) -> float:
    """Return the fraction of non-background pixels on one page."""
    samples = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    data = samples.samples
    if not data:
        return 0.0
    # 扫描件经过再排版后应是白底黑字；以 245 为阈值区分墨与纸。
    ink = sum(1 for value in data if value < 245)
    return ink / len(data)


def main() -> int:
    args = parse_args()
    if not args.pdf.is_file():
        print(f"找不到 PDF: {args.pdf}", file=sys.stderr)
        return 2

    document = pymupdf.open(args.pdf)
    try:
        fractions = [ink_fraction(page, args.dpi) for page in document]
    finally:
        document.close()

    if not fractions:
        print(f"PDF 没有有效页面: {args.pdf}", file=sys.stderr)
        return 2

    ordered = sorted(fractions)
    median = statistics.median(ordered)
    threshold = median * args.ratio

    candidates = [
        {"page": index + 1, "ink": fraction}
        for index, fraction in enumerate(fractions)
        if fraction < threshold
    ]
    candidates.sort(key=lambda item: item["ink"])
    candidates = candidates[: args.top]

    payload = {
        "pdf": str(args.pdf),
        "pages": len(fractions),
        "dpi": args.dpi,
        "ink_median": round(median, 6),
        "ink_min": round(min(fractions), 6),
        "ink_max": round(max(fractions), 6),
        "threshold": round(threshold, 6),
        "sparse_candidate_pages": candidates,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(
        f"页数 {payload['pages']}；墨迹中位数 {payload['ink_median']:.4f}，"
        f"最小 {payload['ink_min']:.4f}，最大 {payload['ink_max']:.4f}"
    )
    if not candidates:
        print("没有低于阈值的稀疏候选页。")
        return 0
    print(
        f"以下 {len(candidates)} 页墨迹明显偏低，优先人工比对；"
        "扉页/章首页/图页本来就稀疏，不等于缺陷："
    )
    for item in candidates:
        print(f"  第 {item['page']} 页  墨迹 {item['ink']:.4f}")
    print("提示：把候选页与原书对应印刷页并排比对，判断是分页漂移还是原本就稀疏。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
