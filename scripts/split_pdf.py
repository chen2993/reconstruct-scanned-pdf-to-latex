#!/usr/bin/env python3
"""Create page images without reading the PDF text layer or running OCR."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


CONTROL_DIR = ".reconstruct-scanned-pdf-to-latex"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "将 PDF 拆为 extraced/page-xxx.png；不读取文字层、不执行 OCR。"
            "默认优先保留整页扫描图的原始像素网格。"
        )
    )
    parser.add_argument("project", type=Path, help="已初始化的项目目录")
    parser.add_argument("pdf", type=Path, help="源扫描 PDF")
    parser.add_argument(
        "--image-source",
        choices=("auto", "embedded", "render"),
        default="auto",
        help=(
            "页面图来源：auto 优先直取整页嵌入图；embedded 要求每页都可直取；"
            "render 强制按 --dpi 渲染（默认 auto）。"
        ),
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="render 页面时的 DPI（默认 300；不影响直取的整页扫描图）",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_directory(stage: Path, target: Path) -> None:
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise RuntimeError(f"输出位置不是普通目录: {target}")
    backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
    had_target = target.exists()
    if had_target:
        os.replace(target, backup)
    try:
        os.replace(stage, target)
    except Exception:
        if had_target and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def density_record(x: float, y: float) -> dict[str, float]:
    return {"x": round(x, 3), "y": round(y, 3)}


def declared_density(value: object) -> dict[str, float] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    x, y = value
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, (int, float))
        or not isinstance(y, (int, float))
        or not math.isfinite(x)
        or not math.isfinite(y)
        or x <= 0
        or y <= 0
    ):
        return None
    return density_record(float(x), float(y))


def image_covers_page(info: dict[str, Any], page: Any) -> bool:
    """Return whether an image covers the visible page with no material margin."""
    bbox = info.get("bbox")
    if not isinstance(bbox, tuple) or len(bbox) != 4:
        return False
    left, top, right, bottom = (float(value) for value in bbox)
    page_rect = page.rect
    tolerance = max(0.5, page_rect.width * 0.001, page_rect.height * 0.001)
    return not (
        abs(left - page_rect.x0) > tolerance
        or abs(top - page_rect.y0) > tolerance
        or abs(right - page_rect.x1) > tolerance
        or abs(bottom - page_rect.y1) > tolerance
    )


def is_normal_image_transform(info: dict[str, Any]) -> bool:
    # Direct extraction keeps the embedded pixel array. Orthogonal transforms are
    # deliberately left to the correction phase, so only the untransformed case
    # is accepted here and mixed/complex pages safely fall back to rendering.
    transform = info.get("transform")
    if not isinstance(transform, tuple) or len(transform) != 6:
        return False
    a, b, c, d, _, _ = (float(value) for value in transform)
    scale = max(abs(a), abs(b), abs(c), abs(d), 1.0)
    axis_tolerance = scale * 1e-6
    return abs(b) <= axis_tolerance and abs(c) <= axis_tolerance and a > 0 and d > 0


def effective_dpi(info: dict[str, Any]) -> tuple[float, float] | None:
    bbox = info.get("bbox")
    width = info.get("width")
    height = info.get("height")
    if (
        not isinstance(bbox, tuple)
        or len(bbox) != 4
        or not isinstance(width, int)
        or not isinstance(height, int)
    ):
        return None
    displayed_width = float(bbox[2]) - float(bbox[0])
    displayed_height = float(bbox[3]) - float(bbox[1])
    if displayed_width <= 0 or displayed_height <= 0:
        return None
    return width * 72.0 / displayed_width, height * 72.0 / displayed_height


def embedded_image_candidate(
    page: Any,
) -> tuple[dict[str, Any] | None, str, tuple[float, float] | None]:
    images = page.get_image_info(xrefs=True)
    if len(images) != 1:
        full_page_densities = [
            effective_dpi(info)
            for info in images
            if isinstance(info, dict) and image_covers_page(info, page)
        ]
        fallback_density = (
            full_page_densities[0]
            if len(full_page_densities) == 1 and full_page_densities[0] is not None
            else None
        )
        return None, f"可见图像数量为 {len(images)}，不是单张整页图", fallback_density
    info = images[0]
    if not isinstance(info, dict):
        return None, "整页图记录无效", None
    xref = info.get("xref")
    width = info.get("width")
    height = info.get("height")
    if (
        isinstance(xref, bool)
        or not isinstance(xref, int)
        or xref <= 0
        or isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
    ):
        return None, "嵌入图像没有可提取的图像对象或像素尺寸", None
    image_density = effective_dpi(info)
    if not image_covers_page(info, page):
        # A small illustration must not force an enormous full-page fallback
        # render merely because its own embedded density is high.
        return None, "单张图像未完整覆盖页面", None
    page_ratio = page.rect.width / page.rect.height
    image_ratio = width / height
    if abs(image_ratio / page_ratio - 1.0) > 0.01:
        return None, "图像像素长宽比与页面差异过大", image_density
    if bool(info.get("has-mask")):
        return None, "整页图带有蒙版", image_density
    if page.get_drawings():
        return None, "页面还包含矢量绘制", image_density
    if not is_normal_image_transform(info):
        return None, "整页图带有旋转、镜像或复杂变换", image_density
    return info, "", image_density


def save_embedded_image(
    document: Any,
    info: dict[str, Any],
    destination: Path,
) -> dict[str, Any]:
    """Write an embedded full-page raster to PNG without resampling its pixels."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "直取扫描页需要 Pillow；安装 Pillow，或显式使用 --image-source render。"
        ) from exc

    xref = int(info["xref"])
    extracted = document.extract_image(xref)
    image_bytes = extracted.get("image") if isinstance(extracted, dict) else None
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise RuntimeError("无法取得整页嵌入图像数据")
    source_density = effective_dpi(info)
    if source_density is None:
        raise RuntimeError("整页嵌入图像的显示尺寸无效")
    page_density = density_record(*source_density)

    with Image.open(io.BytesIO(image_bytes)) as opened:
        opened.load()
        source_format = opened.format or extracted.get("ext") or "unknown"
        source_mode = opened.mode
        declared_dpi = declared_density(opened.info.get("dpi"))
        # PNG cannot encode every source mode. This conversion changes color
        # representation only where necessary; it never rescales page pixels.
        if source_mode in {"1", "L", "LA", "P", "RGB", "RGBA"}:
            output = opened.copy()
        else:
            output = opened.convert("RGBA" if "A" in opened.getbands() else "RGB")
        try:
            output_width_px, output_height_px = output.size
            save_options: dict[str, Any] = {
                "format": "PNG",
                "dpi": (page_density["x"], page_density["y"]),
            }
            icc_profile = opened.info.get("icc_profile")
            if isinstance(icc_profile, bytes):
                save_options["icc_profile"] = icc_profile
            output.save(destination, **save_options)
        finally:
            output.close()

    return {
        "source_kind": "embedded-image",
        "resampled": False,
        "source_image_xref": xref,
        "source_image_format": str(source_format).lower(),
        "source_image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "source_display_rect_pt": [round(float(value), 3) for value in info["bbox"]],
        "source_declared_dpi": declared_dpi,
        "source_width_px": int(info["width"]),
        "source_height_px": int(info["height"]),
        "output_dpi": page_density,
        "_output_width_px": output_width_px,
        "_output_height_px": output_height_px,
    }


def render_page(page: Any, destination: Path, dpi: int) -> dict[str, Any]:
    import fitz

    scale = dpi / 72.0
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False
    )
    try:
        pixmap.set_dpi(dpi, dpi)
        pixmap.save(destination)
        return {
            "source_kind": "rendered-page",
            "resampled": True,
            "source_width_px": pixmap.width,
            "source_height_px": pixmap.height,
            "output_dpi": density_record(float(dpi), float(dpi)),
            "render_dpi": dpi,
            "_output_width_px": pixmap.width,
            "_output_height_px": pixmap.height,
        }
    finally:
        pixmap = None


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    pdf = args.pdf.resolve()
    control = project / CONTROL_DIR
    output = control / "extraced"

    if not project.is_dir() or not control.is_dir():
        print(f"项目尚未初始化: {project}", file=sys.stderr)
        return 2
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        print(f"源文件不是现有 PDF: {pdf}", file=sys.stderr)
        return 2
    if not 72 <= args.dpi <= 600:
        print("--dpi 必须在 72 到 600 之间。", file=sys.stderr)
        return 2
    try:
        pdf.relative_to(output.resolve())
    except ValueError:
        pass
    else:
        print("源 PDF 不得放在 extraced 输出目录内。", file=sys.stderr)
        return 2

    stage = output.parent / f".{output.name}.stage-{uuid.uuid4().hex}"
    try:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("缺少 PyMuPDF，请先安装 pymupdf。") from exc

        source_hash = sha256(pdf)
        stage.mkdir()
        pages: list[dict[str, Any]] = []
        embedded_count = 0
        rendered_count = 0
        with fitz.open(pdf) as document:
            if document.needs_pass:
                raise RuntimeError("源 PDF 已加密，无法拆页。")
            if document.page_count < 1:
                raise RuntimeError("源 PDF 没有页面。")
            width = max(3, len(str(document.page_count)))
            for index in range(document.page_count):
                page = document.load_page(index)
                filename = f"page-{index + 1:0{width}d}.png"
                destination = stage / filename
                page_record: dict[str, Any] | None = None
                candidate_reason = "已强制渲染"
                source_density: tuple[float, float] | None = None
                if args.image_source != "render":
                    candidate, candidate_reason, source_density = embedded_image_candidate(
                        page
                    )
                    if candidate is not None:
                        try:
                            page_record = save_embedded_image(document, candidate, destination)
                        except Exception as exc:
                            candidate_reason = f"整页图直取失败: {type(exc).__name__}: {exc}"
                            if destination.exists():
                                destination.unlink()

                if page_record is None:
                    if args.image_source == "embedded":
                        raise RuntimeError(
                            f"第 {index + 1} 页不能直取整页扫描图: {candidate_reason}"
                        )
                    fallback_dpi = args.dpi
                    if source_density is not None:
                        fallback_dpi = max(
                            fallback_dpi,
                            math.ceil(max(source_density)),
                        )
                    page_record = render_page(page, destination, fallback_dpi)
                    page_record["render_fallback_reason"] = candidate_reason
                    rendered_count += 1
                else:
                    embedded_count += 1

                width_px = page_record.pop("_output_width_px")
                height_px = page_record.pop("_output_height_px")
                page_record.update(
                    {
                        "page_index": index + 1,
                        "filename": filename,
                        "width_px": width_px,
                        "height_px": height_px,
                        "sha256": sha256(destination),
                    }
                )
                pages.append(page_record)

        if sha256(pdf) != source_hash:
            raise RuntimeError("拆页期间源 PDF 发生变化，请重新执行。")
        manifest = {
            "schema_version": 2,
            "kind": "pdf-pages",
            "state": "split",
            "source_pdf": {"path": str(pdf), "sha256": source_hash},
            "page_image_source": args.image_source,
            "fallback_render_dpi": args.dpi,
            # Keep this field for projects initialized with the earlier script.
            "dpi": args.dpi,
            "page_source_summary": {
                "embedded_image": embedded_count,
                "rendered_page": rendered_count,
            },
            "page_count": len(pages),
            "pages": pages,
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        replace_directory(stage, output)
    except Exception as exc:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        print(
            f"拆页失败，原 extraced 目录保持不变: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        f"已拆出 {len(pages)} 页到: {output}；"
        f"直取整页图 {embedded_count} 页，渲染页 {rendered_count} 页。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
