#!/usr/bin/env python3
"""生成视觉能力探针图：内容已知，可自动核对。

为什么不用随便一张页图
----------------------
判断"这条路线有没有视觉"需要区分**看不到**与**看错**。用真实页图没法区分：答错
可能是模型能力问题，也可能是图本身难。所以探针图用**合成图案**，问题可自动核对：

    3 个蓝色圆形 + 2 个洋红色三角形 + 4 个绿色正方形，左上角写 `V7K`

被测单元被要求只回答 `圆=3 三角=2 方=4 字符=V7K`，看不到就回「看不到」。这样两种
失败模式能分开，调度者据此决定是换路线还是重派。

用法::

    python -X utf8 tools/make_vision_probe.py <output.png>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 探针图的正确内容；改动这里必须同步更新派发提示词里的期望答案。
CIRCLES = 3
TRIANGLES = 2
SQUARES = 4
MARKER = "V7K"
ANSWER = f"圆={CIRCLES} 三角={TRIANGLES} 方={SQUARES} 字符={MARKER}"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成视觉能力探针图。")
    parser.add_argument("output", type=Path, help="输出 PNG 路径")
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("需要 Pillow；先运行 pip install -r requirements.txt。", file=sys.stderr)
        return 2

    width, height = 640, 400
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    # 左上角标记：用大号字，保证低分辨率下仍可辨认
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    draw.text((16, 12), MARKER, fill="black", font=font)

    # 形状分散排布，避免被误数成相邻的一堆
    for index in range(CIRCLES):
        x = 120 + index * 150
        y = 120
        draw.ellipse([x, y, x + 70, y + 70], fill=(30, 90, 220))

    for index in range(TRIANGLES):
        x = 180 + index * 220
        y = 230
        draw.polygon([(x, y + 60), (x + 35, y), (x + 70, y + 60)], fill=(200, 0, 150))

    for index in range(SQUARES):
        x = 60 + index * 145
        y = 320
        draw.rectangle([x, y, x + 46, y + 46], fill=(20, 140, 60))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    image.close()
    print(f"已生成探针图: {args.output}")
    print(f"期望答案: {ANSWER}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
