#!/usr/bin/env python3
"""Apply orthogonal rotations to rendered pages."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


CONTROL_DIR = ".reconstruct-scanned-pdf-to-latex"
PAGE_NAME = re.compile(r"page-(\d{3,})\.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "按 page-corrections.json 更新 extraced 中的完整页面集。"
            "只接受 0/90/180/270 度旋转；忽略小倾斜。"
        )
    )
    parser.add_argument("project", type=Path, help="已完成拆页的项目目录")
    parser.add_argument(
        "--config", type=Path, help="修正规则；默认使用控制目录中的 page-corrections.json"
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def correction_set_sha256(
    corrections: dict[int, int],
) -> str:
    normalized = {
        str(number): {"rotate_clockwise": rotation}
        for number, rotation in sorted(corrections.items())
    }
    payload = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def image_dpi_record(value: object) -> dict[str, float] | None:
    if not isinstance(value, tuple) or len(value) != 2:
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
    return {"x": round(float(x), 3), "y": round(float(y), 3)}


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取{label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label}顶层必须是 JSON 对象。")
    return value


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


def load_extraced_pages(directory: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    manifest_path = directory / "manifest.json"
    manifest = read_json(manifest_path, "extraced 清单")
    if manifest.get("kind") != "pdf-pages" or manifest.get("state") not in {
        "split",
        "corrected",
    }:
        raise RuntimeError("extraced 清单类型无效，请重新拆页。")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise RuntimeError("extraced 清单没有页面。")
    expected_names: list[str] = []
    for expected_number, record in enumerate(pages, 1):
        if not isinstance(record, dict):
            raise RuntimeError("extraced 清单中的页面记录无效。")
        filename = record.get("filename")
        if not isinstance(filename, str) or PAGE_NAME.fullmatch(filename) is None:
            raise RuntimeError(f"extraced 清单中的文件名无效: {filename!r}")
        if record.get("page_index") != expected_number:
            raise RuntimeError("extraced 清单的页序不连续。")
        path = directory / filename
        if not path.is_file() or sha256(path) != record.get("sha256"):
            raise RuntimeError(f"extraced 页面缺失或已变化: {filename}")
        expected_names.append(filename)
    actual_names = sorted(path.name for path in directory.glob("page-*.png"))
    if actual_names != sorted(expected_names):
        raise RuntimeError("extraced 目录与清单不一致，请重新拆页。")
    return manifest_path, manifest, pages


def parse_corrections(
    config: dict[str, Any], page_count: int
) -> dict[int, int]:
    page_rules = config.get("pages")
    if not isinstance(page_rules, dict):
        raise RuntimeError("修正规则必须包含对象字段 pages。")
    parsed: dict[int, int] = {}
    for key, rule in page_rules.items():
        match = re.fullmatch(r"(?:page-)?(\d+)(?:\.png)?", key)
        if match is None:
            raise RuntimeError(f"无效页码键: {key!r}")
        number = int(match.group(1))
        if number < 1 or number > page_count:
            raise RuntimeError(f"修正规则页码超出范围: {key}")
        if number in parsed:
            raise RuntimeError(f"同一页存在重复修正规则: {key}")
        if not isinstance(rule, dict):
            raise RuntimeError(f"第 {number} 页修正规则必须是对象。")
        unknown = set(rule) - {"rotate_clockwise"}
        if unknown:
            raise RuntimeError(f"第 {number} 页存在未知字段: {sorted(unknown)}")

        rotation = rule.get("rotate_clockwise", 0)
        if isinstance(rotation, bool) or rotation not in (0, 90, 180, 270):
            raise RuntimeError(
                f"第 {number} 页 rotate_clockwise 只能是 0、90、180 或 270。"
            )
        rotation = int(rotation)
        parsed[number] = rotation
    return parsed


def transform_page(
    source: Path,
    destination: Path,
    rotation: int,
) -> None:
    from PIL import Image

    if rotation == 0:
        try:
            os.link(source, destination)
        except OSError as exc:
            raise RuntimeError(
                "页面修正需要创建硬链接以原子替换未修改页面；"
                "请将项目放在支持硬链接的本地文件系统中。"
            ) from exc
        return
    transpose = {
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }
    with Image.open(source) as opened:
        source_dpi = image_dpi_record(opened.info.get("dpi"))
        image = opened.convert("RGB")
    if rotation:
        rotated = image.transpose(transpose[rotation])
        image.close()
        image = rotated
    try:
        save_options: dict[str, object] = {"format": "PNG"}
        if source_dpi is not None:
            output_dpi = (
                (source_dpi["y"], source_dpi["x"])
                if rotation in (90, 270)
                else (source_dpi["x"], source_dpi["y"])
            )
            save_options["dpi"] = output_dpi
        image.save(destination, **save_options)
    finally:
        image.close()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    control = project / CONTROL_DIR
    pages_dir = control / "extraced"
    output = pages_dir
    config_path = (
        args.config.resolve()
        if args.config is not None
        else control / "page-corrections.json"
    )
    if not project.is_dir() or not control.is_dir():
        print(f"项目尚未初始化: {project}", file=sys.stderr)
        return 2

    stage = output.parent / f".{output.name}.stage-{uuid.uuid4().hex}"
    try:
        try:
            from PIL import Image  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("缺少 Pillow，请先安装 Pillow。") from exc

        config = read_json(config_path, "页面修正规则")
        config_file_hash = sha256(config_path)
        input_manifest, source_manifest, source_pages = load_extraced_pages(pages_dir)
        corrections = parse_corrections(config, len(source_pages))
        config_hash = correction_set_sha256(corrections)
        if source_manifest.get("state") == "corrected":
            if sha256(config_path) != config_file_hash:
                raise RuntimeError("检查期间修正规则发生变化，请重新执行。")
            if source_manifest.get("corrections_sha256") == config_hash:
                print("extraced 已按当前修正规则生成，无需重复处理。")
                return 0
            raise RuntimeError("extraced 已修正；如需修改规则，请先重新执行拆页。")
        input_manifest_hash = sha256(input_manifest)
        stage.mkdir()
        output_pages: list[dict[str, Any]] = []
        for record in source_pages:
            number = record["page_index"]
            filename = record["filename"]
            source = pages_dir / filename
            destination = stage / filename
            rule = corrections.get(number)
            rotation = corrections.get(number, 0)
            transform_page(source, destination, rotation)
            with Image.open(destination) as image:
                width_px, height_px = image.size
                output_dpi = image_dpi_record(image.info.get("dpi"))
            output_record = dict(record)
            output_record.update(
                {
                    "page_index": number,
                    "filename": filename,
                    "width_px": width_px,
                    "height_px": height_px,
                    "output_dpi": output_dpi,
                    "sha256": sha256(destination),
                    "correction": (
                        None
                        if rule is None
                        else {"rotate_clockwise": rotation}
                    ),
                }
            )
            output_pages.append(output_record)

        if (
            sha256(input_manifest) != input_manifest_hash
            or sha256(config_path) != config_file_hash
        ):
            raise RuntimeError("处理期间输入清单或修正规则发生变化，请重新执行。")
        manifest = {
            "schema_version": 2,
            "kind": "pdf-pages",
            "state": "corrected",
            "input_manifest_sha256": input_manifest_hash,
            "source_pdf": source_manifest.get("source_pdf"),
            "page_image_source": source_manifest.get("page_image_source"),
            "fallback_render_dpi": source_manifest.get(
                "fallback_render_dpi", source_manifest.get("dpi")
            ),
            "page_source_summary": source_manifest.get("page_source_summary"),
            "dpi": source_manifest.get("dpi"),
            "corrections_sha256": config_hash,
            "page_count": len(output_pages),
            "pages": output_pages,
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
            f"页面修正失败，原 extraced 目录保持不变: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"已更新 {len(output_pages)} 个 extraced；应用规则 {len(corrections)} 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
