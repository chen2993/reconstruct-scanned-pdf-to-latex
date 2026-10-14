#!/usr/bin/env python3
"""把 PDF 的一个显式页范围导出成新的小 PDF（供无页范围参数的工具使用）。

为什么需要它：候选工具分两类。Docling、Marker、Surya 一类支持 ``--page-range``，
可以直接吃整本 PDF；PaddleOCR 的 PP-StructureV3 一类没有页范围参数，只能整份输入。
对后者，先切出小 PDF 再喂进去，既守住"只处理明确页范围"的候选边界，也避免为了
看三页而让工具啃完整本书。

切出来的文件是临时的中间产物，只允许写进项目 ``tmp/``；它不修改源 PDF，也不读取
文字层（PyMuPDF 的 ``select`` 是按页对象搬运，不做 OCR、不解析内容）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_backend import require_pymupdf  # noqa: E402


class UsageError(RuntimeError):
    """参数或输出位置不符合契约。"""


def parse_pages(value: str) -> list[int]:
    """解析 ``12-14,18`` 形式的 1-based 页范围，返回排序去重后的页号。"""

    pages: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            raise UsageError(f"页范围含空项: {value!r}")
        start_text, separator, end_text = token.partition("-")
        if not start_text.isdigit() or (separator and not end_text.isdigit()):
            raise UsageError(f"非法页范围: {token!r}（示例：12-14,18）")
        start = int(start_text)
        end = int(end_text) if separator else start
        if start < 1 or end < start:
            raise UsageError(f"页范围必须从 1 开始且起点不大于终点: {token!r}")
        pages.extend(range(start, end + 1))
    if not pages:
        raise UsageError("页范围不能为空")
    return sorted(set(pages))


def check_output_location(project: Path, output: Path) -> Path:
    resolved = (output if output.is_absolute() else project / output).resolve()
    root = (project / "tmp").resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UsageError(
            f"页范围子集只能写入 tmp/（绝对路径 {root}）下: {resolved}"
        ) from exc
    return resolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 PDF 的显式页范围导出成 tmp/ 下的小 PDF。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument("input_pdf", type=Path, help="源 PDF；只读，不会修改")
    parser.add_argument(
        "--pages",
        required=True,
        help="从 1 开始的页范围，如 12-14,18（与运行器的 --pages 语义一致）",
    )
    parser.add_argument("--output", type=Path, required=True, help="输出 PDF；必须位于 tmp/ 下")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        print(f"项目目录不存在: {project}", file=sys.stderr)
        return 2
    try:
        pages = parse_pages(args.pages)
        source = args.input_pdf.resolve()
        if not source.is_file() or source.suffix.lower() != ".pdf":
            raise UsageError(f"输入必须是存在的 PDF 文件: {source}")
        output = check_output_location(project, args.output)
        if output == source:
            raise UsageError("输出不能覆盖源 PDF")

        fitz = require_pymupdf()
        with fitz.open(source) as document:
            total = document.page_count
            out_of_range = [page for page in pages if page > total]
            if out_of_range:
                raise UsageError(
                    f"页范围超出源 PDF（共 {total} 页）: "
                    + ", ".join(str(page) for page in out_of_range)
                )
            document.select([page - 1 for page in pages])
            output.parent.mkdir(parents=True, exist_ok=True)
            document.save(output)
    except (UsageError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"已导出 {len(pages)} 页 -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
