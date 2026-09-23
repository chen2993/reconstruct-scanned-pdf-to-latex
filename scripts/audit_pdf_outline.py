#!/usr/bin/env python3
"""Validate PDF outline and target-page rendering without reading page text.

前后置模块不是固定清单：以原书实际拥有的模块为准。本脚本校验的是"项目声明的
模块都真实出现、顺序正确、目标页非空"，而不是强求四个特定书签。原件没有献词
就不该有献词书签；原件有的模块则必须有书签，不能静默漏掉。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_backend import require_pymupdf  # noqa: E402

# 常见前后置模块的参考写法，仅用于提示命名习惯；不是默认值，也不是强制清单。
# 项目必须按原书实际拥有的模块传入清单，原件没有前后置模块时不传即可。
REFERENCE_BOOKMARK_EXAMPLE = "cover=封面 preface=前言 toc=目录 backmatter=书末页"
# 语义键是 ASCII 标识符，与页面源码里的 key 参数一致。
KEY_PATTERN = re.compile(r"[a-z][a-z0-9_]*")


def parse_required_map(entries: list[str]) -> list[tuple[str, str]]:
    """Parse ``key=title`` entries into an ordered list.

    顺序有意义：它与原件的模块顺序一致，用于校验书签树的先后关系。
    """

    # 允许为空：原件可能没有任何前后置模块（例如纯正文的扫描件）。此时不做书签
    # 覆盖检查，但仍然校验 outline 自身的结构完整性。
    pairs: list[tuple[str, str]] = []
    for entry in entries:
        key, separator, title = entry.partition("=")
        key, title = key.strip(), title.strip()
        if not separator or not key or not title:
            raise ValueError(f"书签映射无效: {entry!r}；应为 KEY=TITLE。")
        if KEY_PATTERN.fullmatch(key) is None:
            raise ValueError(f"书签语义键必须是英文 ASCII 标识符: {key!r}")
        pairs.append((key, title))
    keys = [key for key, _ in pairs]
    titles = [title for _, title in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError(f"书签语义键重复: {keys}")
    if len(set(titles)) != len(titles):
        raise ValueError(f"书签显示标题重复: {titles}")
    return pairs


def validate_outline(
    outline: object, page_count: int, required: list[tuple[str, str]]
) -> tuple[dict[str, list[int]], list[str]]:
    """Validate outline structure while touching metadata only.

    PyMuPDF returns ``[level, title, page]`` records for ``get_toc``.  Keep
    every declared title as a list so duplicate top-level entries cannot be
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

    for _, title in required:
        targets = top_level.get(title, [])
        if not targets:
            errors.append(f"缺少顶层书签: {title}")
        elif len(targets) > 1:
            errors.append(f"顶层书签重复: {title}")

    declared_titles = [title for _, title in required]
    pages = [top_level[title][0] for title in declared_titles if title in top_level]
    if len(pages) == len(declared_titles):
        if len(set(pages)) != len(pages):
            errors.append("已登记模块的书签不能指向同一页。")
        if pages != sorted(pages):
            errors.append(
                "已登记模块的书签顺序必须与登记顺序一致："
                + "、".join(declared_titles)
            )

    return top_level, errors


def target_pages_are_nonblank(document: object, pages: list[int]) -> list[int]:
    """Render only the declared target pages and reject completely blank pages."""

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
        default=[],
        metavar="KEY=TITLE",
        help=(
            "本项目实际存在的前后置模块及其书签显示标题，按原件顺序给出，"
            "例如 " + REFERENCE_BOOKMARK_EXAMPLE + "；"
            "原件没有前后置模块时省略本参数，只检查 outline 结构"
        ),
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
                pages = [top_level[title][0] for _, title in required]
                blank_pages = target_pages_are_nonblank(document, pages)
                if blank_pages:
                    errors.append(
                        "已登记模块的书签指向空白页: "
                        + ", ".join(str(page) for page in blank_pages)
                    )
    except Exception as exc:  # PyMuPDF exposes several document-specific errors.
        print(f"无法读取 PDF outline: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    if required:
        print(
            "PDF outline 通过："
            + ", ".join(
                f"{key}={title} -> {top_level[title][0]}" for key, title in required
            )
        )
    else:
        print("PDF outline 结构通过：未登记前后置模块，跳过模块书签覆盖检查。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
