#!/usr/bin/env python3
"""Validate PDF outline and target-page rendering without reading page text."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_backend import require_pymupdf  # noqa: E402

SEMANTIC_KEYS = ("cover", "preface", "dedication", "backmatter")
DEFAULT_REQUIRED_MAP = (
    "cover=封面",
    "preface=前言",
    "dedication=献词",
    "backmatter=书末页",
)


def parse_required_map(entries: list[str]) -> dict[str, str]:
    """Parse the fixed four semantic keys and their visible titles."""

    if len(entries) != len(SEMANTIC_KEYS):
        raise ValueError(
            "必须为 cover、preface、dedication、backmatter 各提供一个标题。"
        )
    mapping: dict[str, str] = {}
    for entry in entries:
        key, separator, title = entry.partition("=")
        key = key.strip()
        title = title.strip()
        if not separator or key not in SEMANTIC_KEYS or not title:
            raise ValueError(f"书签映射无效: {entry!r}")
        if key in mapping:
            raise ValueError(f"书签语义键重复: {key}")
        mapping[key] = title
    if set(mapping) != set(SEMANTIC_KEYS):
        raise ValueError("书签映射必须完整包含四个固定语义键。")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("四个书签显示标题不能重复。")
    return mapping


def validate_outline(
    outline: object, page_count: int, required: dict[str, str]
) -> tuple[dict[str, list[int]], list[str]]:
    """Validate outline structure while touching metadata only.

    PyMuPDF returns ``[level, title, page]`` records for ``get_toc``.  Keep
    every required title as a list so duplicate top-level entries cannot be
    hidden by a dictionary overwrite.
    """

    errors: list[str] = []
    top_level: dict[str, list[int]] = {}
    previous_level: int | None = None

    if not isinstance(outline, list):
        return {}, ["PDF outline 格式无效。"]

    for index, item in enumerate(outline, start=1):
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            errors.append(f"第 {index} 条书签记录格式无效。")
            continue
        level, title, page = item[0], item[1], item[2]
        if not isinstance(level, int) or level < 1:
            errors.append(f"第 {index} 条书签层级无效。")
            continue
        if not isinstance(title, str) or not title.strip():
            errors.append(f"第 {index} 条书签标题为空。")
            continue
        title = title.strip()
        if not isinstance(page, int) or not 1 <= page <= page_count:
            errors.append(f"书签目标页无效: {title}")
        if previous_level is not None and level > previous_level + 1:
            errors.append(f"书签层级跳跃: {title}")
        previous_level = level
        if level == 1:
            top_level.setdefault(title, []).append(page)

    if outline and isinstance(outline[0], (list, tuple)) and outline[0] and outline[0][0] != 1:
        errors.append("PDF outline 必须从顶层书签开始。")

    for title in required.values():
        targets = top_level.get(title, [])
        if not targets:
            errors.append(f"缺少顶层书签: {title}")
        elif len(targets) > 1:
            errors.append(f"顶层书签重复: {title}")

    required_pages = [top_level[required[key]][0] for key in SEMANTIC_KEYS if required[key] in top_level]
    if len(required_pages) == len(SEMANTIC_KEYS):
        if len(set(required_pages)) != len(required_pages):
            errors.append("四个必需模块的书签不能指向同一页。")
        if required_pages != sorted(required_pages):
            errors.append("四个必需模块的书签顺序必须为封面、前言、献词、书末页。")

    return top_level, errors


def target_pages_are_nonblank(document: object, pages: list[int]) -> list[int]:
    """Render only required target pages and reject completely blank pages."""

    fitz = require_pymupdf()

    blank: list[int] = []
    for page_number in pages:
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), alpha=False)
        if not pixmap.samples or not any(value < 250 for value in pixmap.samples):
            blank.append(page_number)
    return blank


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检查 PDF 顶层书签和目标页渲染；不读取正文文字。"
    )
    parser.add_argument("pdf", type=Path, help="待检查的 PDF")
    parser.add_argument(
        "--required-map",
        nargs="+",
        default=list(DEFAULT_REQUIRED_MAP),
        metavar="KEY=TITLE",
        help="四个固定语义键及其 PDF 书签显示标题",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        print(f"PDF 不存在或扩展名无效: {args.pdf}", file=sys.stderr)
        return 2
    try:
        required = parse_required_map(args.required_map)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    fitz = require_pymupdf()

    try:
        with fitz.open(args.pdf) as document:
            outline = document.get_toc(simple=True)
            page_count = document.page_count
            top_level, errors = validate_outline(outline, page_count, required)
            if not errors:
                pages = [top_level[required[key]][0] for key in SEMANTIC_KEYS]
                blank_pages = target_pages_are_nonblank(document, pages)
                if blank_pages:
                    errors.append(
                        "必需书签指向空白页: "
                        + ", ".join(str(page) for page in blank_pages)
                    )
    except Exception as exc:  # PyMuPDF exposes several document-specific errors.
        print(f"无法读取 PDF outline: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "PDF outline 通过："
        + ", ".join(
            f"{key}={title} -> {top_level[title][0]}"
            for key, title in required.items()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
