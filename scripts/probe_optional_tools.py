#!/usr/bin/env python3
"""只读探测可选 PDF/公式解析器，不读取 PDF，也不执行转换。

这个脚本只回答“当前环境有没有候选工具，以及它大致是什么版本”。它不接受输入
PDF 路径，避免探测阶段意外触发 OCR、联网服务或产生正文候选。
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path


COMMAND_CANDIDATES = {
    "mineru": ("mineru", "mineru-kit", "magic-pdf"),
    "marker": ("marker_single", "marker"),
    "docling": ("docling",),
    "nougat": ("nougat",),
    # 第四家 VLM 系 OCR：页范围参数是真的（实测 --page-range），自带中数示例。
    # 权重是改过的 OpenRAIL-M，默认 vllm 后端要起服务；用 --method hf 才纯本地。
    "chandra": ("chandra",),
    # 中文原生、体量最小（0.9B / 约 1.9 GB）、Apache-2.0；但**没有页范围参数**，
    # 必须先 extract_page_range.py 切小 PDF。
    "paddleocr_vl": ("paddleocr",),
    # Surya is an image-level locator (OCR/layout/order), not a PDF-to-LaTeX
    # converter. It is still useful for deciding which narrow crop to inspect.
    "surya": ("surya_ocr", "surya_layout", "surya_order", "surya_table"),
    # PDF-Extract-Kit is commonly used as a Python package rather than a stable
    # cross-platform CLI, so it is probed by package presence only.
    "pdf_extract_kit": (),
}

PACKAGE_CANDIDATES = {
    "mineru": ("mineru", "magic_pdf"),
    "marker": ("marker", "marker_pdf"),
    "docling": ("docling", "docling_core"),
    "nougat": ("nougat", "nougat_ocr"),
    "chandra": ("chandra", "chandra_ocr"),
    "paddleocr_vl": ("paddleocr", "paddle"),
    "surya": ("surya",),
    "pdf_extract_kit": ("pdf_extract_kit",),
    "pix2text": ("pix2text",),
    "pix2tex": ("pix2tex",),
}

TOOL_METADATA = {
    "mineru": {
        "category": "layout-structure-candidate",
        "preferred_for": ["页面块定位", "公式候选", "表格候选", "阅读顺序提示"],
        "fit_for_chinese_scans": "candidate",
        "runner_entrypoints": {
            "page_scoped": "mineru parse",
            "all_pages": "mineru parse --pages all",
        },
        "runner_page_index": "1-based",
    },
    "marker": {
        "category": "layout-structure-candidate",
        "preferred_for": ["阅读顺序候选", "Markdown/JSON 结构对照", "图片区域候选"],
        "fit_for_chinese_scans": "candidate",
        "runner_entrypoints": {"page_scoped": "marker_single"},
        "runner_page_index": "0-based",
    },
    "docling": {
        "category": "layout-structure-candidate",
        "preferred_for": ["页面块定位", "表格结构候选", "文档模型对照"],
        "fit_for_chinese_scans": "candidate",
        "runner_entrypoints": {"page_scoped": "docling convert <source>"},
        "runner_page_index": "1-based contiguous range",
    },
    "nougat": {
        "category": "experimental-scientific-candidate",
        "preferred_for": ["英文科学文献结构候选", "公式候选"],
        "fit_for_chinese_scans": "weak",
    },
    "chandra": {
        "category": "layout-structure-candidate",
        "preferred_for": ["中文数学页候选", "表格候选", "页范围直读", "手写体"],
        "fit_for_chinese_scans": "candidate",
        "notes": (
            "自带中数示例；--page-range 可直接用。权重为改版 OpenRAIL-M，"
            "默认 vllm 后端需要服务，本地推理用 --method hf。"
        ),
        "runner_entrypoints": {"page_scoped": "chandra <pdf> <out> --page-range"},
        "runner_page_index": "1-based",
    },
    "paddleocr_vl": {
        "category": "layout-structure-candidate",
        "preferred_for": ["中文正文候选", "版面分区", "表格候选", "公式候选"],
        "fit_for_chinese_scans": "strong",
        "notes": (
            "中文原生、0.9B 最小体量、Apache-2.0；没有页范围参数，"
            "必须先用 extract_page_range.py 切出小 PDF 再喂。"
        ),
        "runner_entrypoints": {"whole_document": "paddleocr doc_parser -i <pdf>"},
        "runner_page_index": "no-page-range",
    },
    "surya": {
        "category": "image-region-candidate",
        "preferred_for": ["版面区域定位", "阅读顺序候选", "表格/图片区域候选"],
        "fit_for_chinese_scans": "candidate",
        "runner_entrypoints": {
            "crop_only": "surya_ocr/surya_layout/surya_order",
        },
        "runner_page_index": "image-only",
    },
    "pdf_extract_kit": {
        "category": "layout-formula-candidate",
        "preferred_for": ["版面检测候选", "公式/表格区域候选"],
        "fit_for_chinese_scans": "candidate",
        "runner_entrypoints": {},
        "runner_page_index": "crop-or-page-image",
    },
    "formula_helper": {
        "category": "formula-candidate",
        "preferred_for": ["局部公式候选", "公式区域差异审计"],
        "fit_for_chinese_scans": "local-only",
        "runner_entrypoints": {},
        "runner_page_index": "crop-only",
    },
}

FORMULA_COMMAND_CANDIDATES = ("pix2text", "pix2tex_cli", "pix2tex", "texify")


def command_version(path: str) -> dict[str, object]:
    """Probe only a version flag; never pass a document path or shell command."""
    attempts: list[dict[str, object]] = []
    for flag in ("--version", "-V"):
        try:
            result = subprocess.run(
                [path, flag],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            attempts.append({"flag": flag, "error": type(exc).__name__})
            continue
        output = (result.stdout or result.stderr).strip().splitlines()
        attempts.append(
            {
                "flag": flag,
                "returncode": result.returncode,
                "output": output[:3],
            }
        )
        if result.returncode == 0 or output:
            break
    return {"path": path, "version_probe": attempts}


def package_probe(names: tuple[str, ...]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name in names:
        try:
            present = importlib.util.find_spec(name) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            present = False
        version = None
        if present:
            try:
                version = importlib.metadata.version(name.replace("_", "-"))
            except importlib.metadata.PackageNotFoundError:
                version = None
        result.append({"name": name, "present": present, "version": version})
    return result


def probe() -> dict[str, object]:
    tools: dict[str, object] = {}
    for tool, candidates in COMMAND_CANDIDATES.items():
        commands: list[dict[str, object]] = []
        for candidate in candidates:
            path = shutil.which(candidate)
            commands.append(
                {"name": candidate, "found": path is not None}
                | (command_version(path) if path else {})
            )
        tools[tool] = {
            **TOOL_METADATA[tool],
            "commands": commands,
            "packages": package_probe(PACKAGE_CANDIDATES.get(tool, ())),
        }
    tools["formula_helper"] = {
        **TOOL_METADATA["formula_helper"],
        "commands": [
            {"name": candidate, "found": shutil.which(candidate) is not None}
            | (
                command_version(shutil.which(candidate))
                if shutil.which(candidate)
                else {}
            )
            for candidate in FORMULA_COMMAND_CANDIDATES
        ],
        "packages": package_probe(
            PACKAGE_CANDIDATES["pix2text"] + PACKAGE_CANDIDATES["pix2tex"]
        ),
    }
    return {
        "schema": "optional-tool-probe.v2",
        "read_pdf": False,
        "ran_conversion": False,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "tools": tools,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="只读探测 PDF 结构、版面和局部公式候选工具；不接受 PDF 输入。"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON（默认也是 JSON）")
    parser.add_argument("--output", type=Path, help="把 JSON 写入指定文件；不写入正文目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.dumps(probe(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

