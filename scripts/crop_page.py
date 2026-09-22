#!/usr/bin/env python3
"""查看单页扫描图的标准化工具：总览、横带、区域三种取法。

页图常见 4000×6000 px 量级，远大于多模态读取的舒适尺寸。读取环节会**按长边
等比例缩小**图片，由此得到两条实用结论：

* **横带只切高度，不减少宽度**，所以它不会让公式变清楚；横带的用处是保留整行
  版式、顺序读完一页。
* **宽度决定清晰度**。要看清公式、角标、表格线，就把那一块截窄一些（用
  ``--region`` 指定列范围），而不是只把页面切得更短。

取哪一块由使用者判断，本工具只负责按参数裁出图，并报告实际输出尺寸、等效 dpi
和"是否会被读取环节缩小"。

用法::

    # 整页总览：看清版面分区、栏数与图形位置
    python -X utf8 scripts/crop_page.py <project> pages-013 tmp/over.png --overview

    # 横带：保留整行版式，顺序读一页的内容
    python -X utf8 scripts/crop_page.py <project> pages-013 tmp/b1.png --band 1/3

    # 区域：只截公式/表格/图（比例基于整页，原点在左上角）
    python -X utf8 scripts/crop_page.py <project> pages-013 tmp/z.png \
        --region 0.08,0.30,0.55,0.45

只处理单页：不读源 PDF、不做 OCR、不拼接多页、不生成联系页。输出只允许写进项目
``tmp/``——它是读取用的临时视觉证据，不属于交付物。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from page_workspace import control_dir  # noqa: E402


SECTIONS = ("front", "pages", "back")

# 总览只用来定位版面，不需要更大；这个宽度足够看清栏数与图形位置。
DEFAULT_OVERVIEW_WIDTH = 1100

# 读取环节的参考长边上限。超过这个尺寸的图会被等比例缩小，等效 dpi 随之下降；
# 这里只用来在输出里提示，不改变裁剪结果。
READER_LONG_EDGE_HINT = 1600

# 页面清单里记录了每页的实际输出 dpi；PNG 元数据缺失时用它兜底。
MANIFEST_FILENAME = "page-dpi.json"


class UsageError(RuntimeError):
    """输入或路径不符合契约；退出码与其它脚本一致为 2。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="裁出单页 PNG 的总览、一条横带或一个区域。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument("page", help="最终页面标识，例如 pages-013")
    parser.add_argument("output", type=Path, help="输出 PNG 路径；必须放在 tmp/ 下")
    parser.add_argument("--band", metavar="I/N", help="把整页等分 N 条横带并取第 I 条")
    parser.add_argument(
        "--region",
        metavar="X0,Y0,X1,Y1",
        help="按比例裁剪，取值 0–1，原点在左上角",
    )
    parser.add_argument("--scale", type=float, default=1.0, help="裁剪后再缩放（默认 1.0）")
    parser.add_argument(
        "--overview",
        action="store_true",
        help=f"整页缩到 {DEFAULT_OVERVIEW_WIDTH} px 宽的定位用总览",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    return parser.parse_args()


def resolve_page(project: Path, identifier: str) -> Path:
    section = identifier.split("-", 1)[0]
    if section not in SECTIONS:
        raise UsageError(f"页面标识必须以 front-/pages-/back- 开头: {identifier}")
    path = control_dir(project) / f"{identifier}.png"
    if not path.is_file():
        raise UsageError(f"找不到页面 PNG: {path}")
    return path


def check_output_location(project: Path, output: Path) -> Path:
    """输出只允许落在项目的 tmp/ 下，避免临时裁图混进交付树。"""

    resolved = (output if output.is_absolute() else project / output).resolve()
    allowed = (project / "tmp").resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise UsageError(
            f"裁图只能写入项目 tmp/ 下（当前 {resolved}）；"
            "它只是读取用的临时视觉证据，不进入交付树。"
        )
    return resolved


def parse_band(value: str) -> tuple[int, int]:
    index, _, total = value.partition("/")
    try:
        index_number, total_number = int(index), int(total)
    except ValueError:
        raise UsageError(f"--band 需要 I/N 形式: {value!r}") from None
    if total_number < 1 or not 1 <= index_number <= total_number:
        raise UsageError(f"--band 超出范围: {value!r}")
    return index_number, total_number


def parse_region(value: str) -> tuple[float, float, float, float]:
    parts = value.split(",")
    if len(parts) != 4:
        raise UsageError(f"--region 需要 X0,Y0,X1,Y1 四个比例: {value!r}")
    try:
        numbers = tuple(float(part) for part in parts)
    except ValueError:
        raise UsageError(f"--region 含非数字: {value!r}") from None
    x0, y0, x1, y1 = numbers
    if not all(0.0 <= item <= 1.0 for item in numbers):
        raise UsageError(f"--region 的每个比例必须在 0–1 之间: {value!r}")
    if x1 <= x0 or y1 <= y0:
        raise UsageError(f"--region 的右下边界必须大于左上边界: {value!r}")
    return x0, y0, x1, y1


def source_dpi(path: Path, width: int, height: int) -> float | None:
    """页图的源分辨率，用于报出等效 dpi。

    优先读 PNG 的 dpi 元数据（拆页脚本会写入实际页面密度）；没有元数据时返回
    ``None``，由调用方决定是否提示，而不是编一个看起来精确的数字。
    """

    from PIL import Image

    with Image.open(path) as image:
        declared = image.info.get("dpi")
    if isinstance(declared, tuple) and len(declared) == 2:
        values = []
        for value in declared:
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        if len(values) == 2 and all(value > 1 for value in values):
            return max(values)
    return None


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        print(f"项目目录不存在: {project}", file=sys.stderr)
        return 2

    try:
        from PIL import Image
    except ImportError:
        print("缺少 Pillow；先运行 pip install -r requirements.txt。", file=sys.stderr)
        return 2

    try:
        source = resolve_page(project, args.page)
        output = check_output_location(project, args.output)

        selectors = [bool(args.band), bool(args.region), bool(args.overview)]
        if sum(selectors) > 1:
            raise UsageError("--overview、--band、--region 三者只能用一个。")
        if args.scale <= 0:
            raise UsageError("--scale 必须大于 0。")

        x0, y0, x1, y1 = 0.0, 0.0, 1.0, 1.0
        mode = "full"
        if args.overview:
            mode = "overview"
        if args.region:
            mode = "region"
            x0, y0, x1, y1 = parse_region(args.region)
        if args.band:
            mode = "band"
            index, total = parse_band(args.band)
            y0, y1 = (index - 1) / total, index / total
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    with Image.open(source) as image:
        page_width, page_height = image.size
        dpi = source_dpi(source, page_width, page_height)
        box = (
            int(round(x0 * page_width)),
            int(round(y0 * page_height)),
            int(round(x1 * page_width)),
            int(round(y1 * page_height)),
        )
        crop = image.crop(box)
        scale = 1.0 if args.overview else args.scale
        if args.overview and crop.width > DEFAULT_OVERVIEW_WIDTH:
            scale = DEFAULT_OVERVIEW_WIDTH / crop.width
        if scale != 1.0:
            crop = crop.resize(
                (
                    max(1, int(round(crop.width * scale))),
                    max(1, int(round(crop.height * scale))),
                ),
                Image.LANCZOS,
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        crop.save(output)
        out_width, out_height = crop.size
        crop.close()

    # 裁剪与等比例缩放都不改变像素密度：一块 600 dpi 的页图裁出来仍是 600 dpi。
    # 真正会降低清晰度的是读取环节自己的缩小，因此等效 dpi 只由那个系数决定。
    effective = None
    if dpi is not None:
        shrink = min(1.0, READER_LONG_EDGE_HINT / max(out_width, out_height))
        effective = round(dpi * shrink, 1)

    payload = {
        "page": args.page,
        "mode": mode,
        "source": str(source),
        "output": str(output),
        "page_px": [page_width, page_height],
        "source_dpi": round(dpi, 1) if dpi is not None else None,
        "output_px": [out_width, out_height],
        "box_px": list(box),
        "scale": round(scale, 4),
        "reader_shrink": round(shrink, 4) if dpi is not None else None,
        "effective_dpi": effective,
        "will_be_shrunk_by_reader": max(out_width, out_height) > READER_LONG_EDGE_HINT,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(
        f"{args.page} [{mode}] -> {output}  {out_width}x{out_height} px"
        f"（scale {scale:.3g}，页面原图 {page_width}x{page_height}）"
    )
    if dpi is not None:
        print(f"源 {dpi:.0f} dpi；这一块等效约 {effective:.0f} dpi。")
    else:
        print("页图没有 dpi 元数据，无法换算等效分辨率；以实际能否看清为准。")

    if mode == "overview":
        print("总览只用于定位版面，不要用它读公式。")
    elif payload["will_be_shrunk_by_reader"]:
        print(
            f"注意: 长边 {max(out_width, out_height)} px 超过读取上限 "
            f"{READER_LONG_EDGE_HINT} px，读取时会被缩小，细节会再降一档；"
            "要看公式请用 --region 把宽度截得更窄。"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
