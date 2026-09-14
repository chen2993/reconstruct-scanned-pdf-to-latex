#!/usr/bin/env python3
"""生成用于演练的图片型 PDF：无文字层，每页一张整页扫描图。

内容由内置字体绘制成像素，因此 PDF 里没有可选文字，符合"扫描件"的输入条件；
它只用于验证工具链，不是真实教材。

用法::

    python -X utf8 tools/make_fixture_pdf.py <output.pdf> [pages]
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

PAGE_WIDTH_PX = 1240  # A4 at 150 dpi
PAGE_HEIGHT_PX = 1754
DPI = 150

FRONT_PAGES = {
    1: ["封面"],
    2: ["版权信息 开本 185mm x 260mm"],
    3: ["前言"],
    4: ["目录"],
    5: ["目录"],
    6: ["目录"],
}

def body_page(number: int) -> list[str]:
    return [
        f"第 {number} 页",
        "",
        "1.1 知识块",
        "定义 1.1 这是用于演练的定义文本，只验证排版契约。",
        "例 1.1 这是例题题干，答案必须出现在完整书里。",
        "答：这是例题的解答，做题本必须隐藏它。",
        "正文段落继续，用于填充页面高度以便看出分页行为。",
    ]

def page_lines(index: int, total: int) -> list[str]:
    if index in FRONT_PAGES:
        return FRONT_PAGES[index]
    if index == total:
        return ["书末页"]
    return body_page(index - len(FRONT_PAGES))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成图片型 PDF 演练件。")
    parser.add_argument("output", type=Path, help="输出 PDF 路径")
    parser.add_argument("pages", type=int, nargs="?", default=12, help="总页数（默认 12）")
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    import fitz
    from PIL import Image, ImageDraw

    document = fitz.open()
    for index in range(1, args.pages + 1):
        image = Image.new("L", (PAGE_WIDTH_PX, PAGE_HEIGHT_PX), 255)
        draw = ImageDraw.Draw(image)
        draw.rectangle([60, 60, PAGE_WIDTH_PX - 60, PAGE_HEIGHT_PX - 60], outline=0, width=3)
        y = 140
        for line in page_lines(index, args.pages):
            draw.text((140, y), line, fill=0)
            y += 56
        for row in range(y + 40, PAGE_HEIGHT_PX - 120, 70):
            draw.line([140, row, PAGE_WIDTH_PX - 160, row], fill=160, width=5)
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
        page = document.new_page(
            width=PAGE_WIDTH_PX * 72 / DPI,
            height=PAGE_HEIGHT_PX * 72 / DPI,
        )
        page.insert_image(page.rect, stream=buffer.getvalue())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    document.save(args.output)
    document.close()
    print(f"已生成 {args.pages} 页图片型 PDF: {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
