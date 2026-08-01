#!/usr/bin/env python3
"""Create temporary visual contact sheets without text extraction."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


CONTROL_DIR = ".reconstruct-scanned-pdf-to-latex"
TEMP_PAGE_NAME = re.compile(r"page-(\d{3,})\.png")
FINAL_PAGE_NAME = re.compile(r"(front|pages|back)-(\d{3,})\.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为最终页面图片生成临时视觉联系表。")
    parser.add_argument("project", type=Path, help="已初始化的项目目录")
    parser.add_argument(
        "--source", choices=("pdf_pages", "final"), default="pdf_pages"
    )
    parser.add_argument("--pages-per-sheet", type=int, default=40)
    parser.add_argument("--columns", type=int, default=5)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取页面清单: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("页面清单顶层必须是对象。")
    return value


def load_pages(project: Path, source: str) -> tuple[Path, Path | None, list[dict[str, Any]]]:
    control = project / CONTROL_DIR
    if source == "pdf_pages":
        directory = control / "pdf_pages"
        manifest_path: Path | None = directory / "manifest.json"
        manifest = read_json(manifest_path)
        if manifest.get("kind") != "pdf-pages" or manifest.get("state") not in {"split", "corrected"}:
            raise RuntimeError("pdf_pages 清单状态无效。")
        records = manifest.get("pages")
        name_key = "filename"
    else:
        directory = control
        manifest_path = None
        records = []
        for path in directory.glob("*.png"):
            if FINAL_PAGE_NAME.fullmatch(path.name):
                records.append({"filename": path.name, "sha256": sha256(path)})
        records.sort(key=lambda record: final_page_sort_key(record["filename"]))
        name_key = "filename"
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"{source} 没有页面。")
    loaded: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("页面记录无效。")
        filename = record.get(name_key)
        expected_hash = record.get("sha256")
        pattern = TEMP_PAGE_NAME if source == "pdf_pages" else FINAL_PAGE_NAME
        if not isinstance(filename, str) or pattern.fullmatch(filename) is None:
            raise RuntimeError(f"页面文件名无效: {filename!r}")
        path = directory / filename
        if not path.is_file() or not isinstance(expected_hash, str) or sha256(path) != expected_hash:
            raise RuntimeError(f"页面缺失或已变化: {path}")
        loaded.append({"filename": filename, "path": path})
    return directory, manifest_path, loaded


def final_page_sort_key(filename: str) -> tuple[int, int]:
    match = FINAL_PAGE_NAME.fullmatch(filename)
    if match is None:
        raise RuntimeError(f"最终页面文件名无效: {filename!r}")
    section_order = {"front": 0, "pages": 1, "back": 2}
    return section_order[match.group(1)], int(match.group(2))


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


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    control = project / CONTROL_DIR
    if not project.is_dir() or not control.is_dir():
        print(f"项目尚未初始化: {project}", file=sys.stderr)
        return 2
    if args.pages_per_sheet < 1 or args.pages_per_sheet > 200:
        print("--pages-per-sheet 必须在 1 到 200 之间。", file=sys.stderr)
        return 2
    if args.columns < 1 or args.columns > args.pages_per_sheet:
        print("--columns 必须是正数且不大于每张联系表的页数。", file=sys.stderr)
        return 2
    stage: Path | None = None
    try:
        from PIL import Image, ImageDraw
        _, input_manifest, pages = load_pages(project, args.source)
        manifest_hash = sha256(input_manifest) if input_manifest else None
        output_root = control / "tmp-contact-sheets"
        target = output_root / args.source
        output_root.mkdir(parents=True, exist_ok=True)
        stage = output_root / f".{args.source}.stage-{uuid.uuid4().hex}"
        stage.mkdir()
        cell_width, cell_height = 240, 330
        sheet_records: list[dict[str, Any]] = []
        sheet_count = (len(pages) + args.pages_per_sheet - 1) // args.pages_per_sheet
        for sheet_index in range(sheet_count):
            subset = pages[sheet_index * args.pages_per_sheet : (sheet_index + 1) * args.pages_per_sheet]
            rows = (len(subset) + args.columns - 1) // args.columns
            canvas = Image.new("RGB", (args.columns * cell_width, rows * cell_height), "white")
            draw = ImageDraw.Draw(canvas)
            for cell_index, record in enumerate(subset):
                row, column = divmod(cell_index, args.columns)
                left = column * cell_width
                top = row * cell_height
                with Image.open(record["path"]) as opened:
                    image = opened.convert("RGB")
                image.thumbnail((cell_width - 12, cell_height - 30), Image.Resampling.LANCZOS)
                x = left + (cell_width - image.width) // 2
                canvas.paste(image, (x, top + 5))
                image.close()
                draw.text((left + 6, top + cell_height - 22), record["filename"], fill="black")
            destination = stage / f"sheet-{sheet_index + 1:03d}.png"
            canvas.save(destination, format="PNG")
            canvas.close()
            sheet_records.append({"filename": destination.name, "sha256": sha256(destination)})
        if input_manifest and sha256(input_manifest) != manifest_hash:
            raise RuntimeError("生成期间输入清单发生变化。")
        (stage / "manifest.json").write_text(
            json.dumps({"kind": "contact-sheets", "source": args.source, "sheets": sheet_records}, indent=2) + "\n",
            encoding="utf-8", newline="\n"
        )
        replace_directory(stage, target)
        stage = None
    except Exception as exc:
        if stage is not None and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        print(f"联系表生成失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"已生成 {len(sheet_records)} 张临时联系表: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
