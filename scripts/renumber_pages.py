#!/usr/bin/env python3
"""Name corrected pages and create the LaTeX entry skeleton.

The input manifest is transient.  Successful completion leaves only final
front/pages/back image names and semantic TeX modules; no page map is kept.
"""

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
PAGE_NAME = re.compile(r"page-(\d{3,})\.png")
BODY_TEX_NAME = re.compile(r"pages-(\d{3,})\.tex")
# Logical module names become LaTeX input names and must not introduce a
# hyphenated identifier into the generated source.
SEMANTIC_NAME = re.compile(r"[a-z][a-z0-9_]*")
PAGE_LIKE_MODULE_NAME = re.compile(r"(?:front|back|page|pages)(?:_?\d+)?")
LATEX_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
MAIN_BEGIN = "% BEGIN GENERATED PAGE IMPORTS"
MAIN_END = "% END GENERATED PAGE IMPORTS"
IMPORT_SIGNATURE = "% Generated imports sha256:"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将暂存页按 front/pages/back 命名，并生成 LaTeX 入口骨架。"
    )
    parser.add_argument("project", type=Path, help="已完成页面方向检查的项目目录")
    parser.add_argument(
        "--discard",
        metavar="START-END[,START-END...]",
        help=(
            "舍去临时页序号；支持逗号分隔的单页或范围，例如 2,5-6。"
            "这些页不参与 front/body/back 编号。"
        ),
    )
    parser.add_argument(
        "--front",
        metavar="START-END",
        help="前置页暂存范围（舍弃前的临时页序号）；可省略",
    )
    parser.add_argument(
        "--front-names",
        metavar="NAME[,NAME...]",
        help="兼容格式：前置页一页一个语义类型名；禁止页码式名称",
    )
    parser.add_argument(
        "--front-modules",
        metavar="NAME=START-END,...",
        help="前置语义模块范围（舍弃后的 front 分区连续序号），例如 cover=1,dedication=2-3,toc=4-8；禁止页码式名称",
    )
    parser.add_argument(
        "--body",
        required=True,
        metavar="START-END",
        help="正文暂存范围（舍弃前的临时页序号）",
    )
    parser.add_argument(
        "--back",
        metavar="START-END",
        help="后置页暂存范围（舍弃前的临时页序号）；可省略",
    )
    parser.add_argument(
        "--back-names",
        metavar="NAME[,NAME...]",
        help="兼容格式：后置页一页一个语义类型名；禁止页码式名称",
    )
    parser.add_argument(
        "--back-modules",
        metavar="NAME=START-END,...",
        help="后置语义模块范围（舍弃后的 back 分区连续序号），例如 afterword=1-3,references=4-6；禁止页码式名称",
    )
    parser.add_argument(
        "--class-name",
        default="reconstructedbook",
        metavar="NAME",
        help="首次创建 main.tex 时使用的类名",
    )
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
        raise RuntimeError(f"无法读取 JSON 文件: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("JSON 文件顶层必须是对象。")
    return value


def parse_range(value: str | None, label: str) -> list[int]:
    if value is None or value.lower() == "none":
        return []
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", value)
    if match is None:
        raise RuntimeError(f"{label} 范围必须写成 START-END。")
    start = int(match.group(1))
    end = int(match.group(2) or match.group(1))
    if start < 1 or end < start:
        raise RuntimeError(f"{label} 范围无效: {value}")
    return list(range(start, end + 1))


def parse_discard(value: str | None, page_count: int) -> set[int]:
    if value is None or value.strip().lower() in {"", "none"}:
        return set()
    discarded: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            raise RuntimeError("discard 不能包含空范围。")
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", item)
        if match is None:
            raise RuntimeError(
                f"discard 范围无效: {item!r}；应写成 START-END[,START-END...]。"
            )
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        if start < 1 or end < start or end > page_count:
            raise RuntimeError(f"discard 范围超出暂存页: {item!r}")
        discarded.update(range(start, end + 1))
    return discarded


def validate_module_name(name: str, option: str) -> None:
    if SEMANTIC_NAME.fullmatch(name) is None:
        raise RuntimeError(f"{option} 中的名称无效: {name!r}")
    if PAGE_LIKE_MODULE_NAME.fullmatch(name) is not None:
        raise RuntimeError(
            f"{option} 必须使用语义类型名（例如 cover、toc、afterword），禁止页码式名称: {name!r}"
        )


def parse_names(value: str | None, count: int, option: str, section: str) -> list[str]:
    if count == 0:
        if value is not None and value.strip().lower() not in {"", "none"}:
            raise RuntimeError(f"{option} 不能在没有 {section} 页时使用。")
        return []
    if value is None or not value.strip() or value.strip().lower() == "none":
        raise RuntimeError(f"{section} 页存在时必须提供 {option} 或对应的 modules 选项。")
    names = [item.strip() for item in value.split(",")]
    if len(names) != count:
        raise RuntimeError(f"{option} 需要 {count} 个名称，实际得到 {len(names)} 个。")
    for name in names:
        validate_module_name(name, option)
    if len(names) != len(set(names)):
        raise RuntimeError(f"{option} 不能包含重复名称。")
    return names


def parse_modules(value: str | None, count: int, option: str, section: str) -> list[dict[str, Any]]:
    if count == 0:
        if value is not None and value.strip().lower() not in {"", "none"}:
            raise RuntimeError(f"{option} 不能在没有 {section} 页时使用。")
        return []
    if value is None or not value.strip() or value.strip().lower() == "none":
        raise RuntimeError(f"{section} 页存在时必须提供 {option} 或对应的 names 选项。")
    modules: list[dict[str, Any]] = []
    for item in value.split(","):
        match = re.fullmatch(r"([a-z][a-z0-9_]*)=(\d+)(?:-(\d+))?", item.strip())
        if match is None:
            raise RuntimeError(f"{option} 项目无效: {item!r}；应为 NAME=START-END。")
        validate_module_name(match.group(1), option)
        start = int(match.group(2))
        end = int(match.group(3) or match.group(2))
        if start < 1 or end < start or end > count:
            raise RuntimeError(f"{option} 范围超出 {section} 分区: {item!r}")
        modules.append({"name": match.group(1), "start": start, "end": end})
    if len({module["name"] for module in modules}) != len(modules):
        raise RuntimeError(f"{option} 不能包含重复模块名。")
    cursor = 1
    for module in modules:
        if module["start"] != cursor:
            raise RuntimeError(f"{option} 必须从 1 开始连续覆盖 {section} 分区。")
        cursor = module["end"] + 1
    if cursor != count + 1:
        raise RuntimeError(f"{option} 必须完整覆盖 {section} 分区。")
    return modules


def resolve_modules(
    section: str,
    count: int,
    module_value: str | None,
    names_value: str | None,
) -> list[dict[str, Any]]:
    if module_value is not None and names_value is not None:
        raise RuntimeError(f"{section} 不能同时使用 modules 和 names。")
    if module_value is not None:
        return parse_modules(module_value, count, f"{section}-modules", section)
    if names_value is not None:
        names = parse_names(names_value, count, f"{section}-names", section)
        return [{"name": name, "start": i, "end": i} for i, name in enumerate(names, 1)]
    if count:
        raise RuntimeError(f"{section} 页存在时必须提供 --{section}-modules。")
    return []


def module_for_page(modules: list[dict[str, Any]], section_page: int) -> tuple[str, int]:
    for module in modules:
        if module["start"] <= section_page <= module["end"]:
            return module["name"], section_page - module["start"] + 1
    raise RuntimeError(f"无法为分区页 {section_page} 找到逻辑模块。")


def load_pages(directory: Path) -> list[Path]:
    manifest_path = directory / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("kind") != "pdf-pages" or manifest.get("state") != "corrected":
        raise RuntimeError("请先完成页面方向检查并运行页面修正脚本。")
    records = manifest.get("pages")
    if not isinstance(records, list) or not records:
        raise RuntimeError("暂存页清单没有页面。")
    paths: list[Path] = []
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict) or record.get("page_index") != index:
            raise RuntimeError("暂存页清单顺序无效。")
        filename = record.get("filename")
        if not isinstance(filename, str) or PAGE_NAME.fullmatch(filename) is None:
            raise RuntimeError(f"暂存页文件名无效: {filename!r}")
        path = directory / filename
        if not path.is_file() or sha256(path) != record.get("sha256"):
            raise RuntimeError(f"暂存页缺失或已变化: {filename}")
        paths.append(path)
    actual = sorted(path.name for path in directory.glob("page-*.png"))
    expected = sorted(path.name for path in paths)
    if actual != expected:
        raise RuntimeError("暂存页目录与清单不一致。")
    return paths


def page_stub(identifier: str) -> str:
    return (
        "% Generated page stub; replace with reconstructed content.\n"
        f"% Source page: {identifier}\n"
    )


def module_stub(name: str, identifiers: list[str]) -> str:
    lines = [
        "% Generated logical module stub; replace with reconstructed content.",
        f"% Module: {name}",
        "% Source pages:",
    ]
    lines.extend(f"%   {identifier}" for identifier in identifiers)
    return "\n".join(lines) + "\n"


def is_stub(text: str) -> bool:
    return text.startswith("% Generated page stub;") or text.startswith(
        "% Generated logical module stub;"
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"无法读取既有 TeX 文件: {path}: {exc}") from exc


def write_atomic(path: Path, content: str) -> None:
    temporary = path.parent / f".{path.name}.stage-{uuid.uuid4().hex}"
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def import_block(front: list[str], body_count: int, back: list[str]) -> str:
    payload = ["% 前后置逐条导入；正文使用类文件的范围命令。"]
    payload.extend(f"\\input{{front/{name}}}" for name in front)
    if body_count:
        payload.append(f"\\bookinput{{1}}{{{body_count}}}")
    payload.extend(f"\\input{{back/{name}}}" for name in back)
    signature = hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()
    lines = [MAIN_BEGIN, f"{IMPORT_SIGNATURE} {signature}", *payload]
    lines.append(MAIN_END)
    return "\n".join(lines)


def main_template(class_name: str, block: str) -> str:
    return (
        f"% Generated single entry point; implement {class_name}.cls during style reconstruction.\n"
        "% A build driver may override BookBuildOptions before inputting this file.\n"
        "\\providecommand{\\BookBuildOptions}{book,print}\n"
        "\\edef\\BookApplyBuildOptions{\\noexpand\\PassOptionsToClass"
        "{\\BookBuildOptions}{"
        + class_name
        + "}}\n"
        "\\BookApplyBuildOptions\n"
        "\\let\\BookApplyBuildOptions\\relax\n"
        f"\\documentclass{{{class_name}}}\n\n\\begin{{document}}\n\n{block}\n\n\\end{{document}}\n"
    )


def is_signed_import_block(block: str) -> bool:
    lines = block.splitlines()
    if len(lines) < 4 or lines[0] != MAIN_BEGIN or lines[-1] != MAIN_END:
        return False
    marker = lines[1]
    if not marker.startswith(IMPORT_SIGNATURE + " "):
        return False
    expected = marker[len(IMPORT_SIGNATURE) + 1 :]
    payload = lines[2:-1]
    actual = hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()
    return bool(re.fullmatch(r"[0-9a-f]{64}", expected)) and expected == actual


def replace_import_block(text: str, block: str, legacy_block: str) -> str:
    begin = text.find(MAIN_BEGIN)
    end = text.find(MAIN_END)
    if begin < 0 or end < begin:
        raise RuntimeError("main.tex 缺少完整的生成入口标记。")
    if text.find(MAIN_BEGIN, begin + len(MAIN_BEGIN)) >= 0 or text.find(MAIN_END, end + len(MAIN_END)) >= 0:
        raise RuntimeError("main.tex 的生成入口标记重复。")
    end += len(MAIN_END)
    current_block = text[begin:end].replace("\r\n", "\n")
    # A signed block is script-owned and may be regenerated when the page
    # ranges change.  An unsigned block is accepted only when it exactly
    # matches the previous script output; any other edit may be a human
    # reordering and must stop instead of being silently overwritten.
    if not is_signed_import_block(current_block) and current_block != legacy_block:
        raise RuntimeError(
            "main.tex 的生成入口区块已被人工修改；请先移除或恢复该区块后再重编号。"
        )
    newline = "\r\n" if "\r\n" in text else "\n"
    return text[:begin] + block.replace("\n", newline) + text[end:]


def install_images(control: Path, staged: Path, image_names: list[str]) -> list[Path]:
    installed: list[Path] = []
    try:
        for name in image_names:
            source = staged / name
            target = control / name
            if target.exists():
                if target.is_symlink() or not target.is_file():
                    raise RuntimeError(f"最终页面目标不是普通文件: {target}")
                if sha256(target) != sha256(source):
                    raise RuntimeError(f"已有最终页面与新页面冲突: {target}")
                source.unlink()
                continue
            os.replace(source, target)
            installed.append(target)
    except Exception:
        for path in installed:
            if path.exists():
                path.unlink()
        raise
    return installed


def restore_files(originals: dict[Path, bytes | None]) -> None:
    for path, content in originals.items():
        if content is None:
            if path.exists() or path.is_symlink():
                path.unlink()
            continue
        temporary = path.parent / f".{path.name}.restore-{uuid.uuid4().hex}"
        temporary.write_bytes(content)
        os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    control = project / CONTROL_DIR
    pages_dir = control / "extraced"
    latex = project / "latex"
    if not project.is_dir() or not control.is_dir():
        print(f"项目尚未初始化: {project}", file=sys.stderr)
        return 2
    for directory in (latex, latex / "front", latex / "pages", latex / "back"):
        if directory.is_symlink() or not directory.is_dir():
            print(f"LaTeX 目录缺失或不是普通目录: {directory}", file=sys.stderr)
            return 2

    stage = control / f".final-pages-stage-{uuid.uuid4().hex}"
    originals: dict[Path, bytes | None] = {}
    installed_images: list[Path] = []
    try:
        if LATEX_IDENTIFIER.fullmatch(args.class_name) is None:
            raise RuntimeError(
                f"--class-name 不是合法 LaTeX 标识符: {args.class_name!r}"
            )
        paths = load_pages(pages_dir)
        discarded = parse_discard(args.discard, len(paths))
        kept_indexes = [
            index for index in range(1, len(paths) + 1) if index not in discarded
        ]
        front_range = parse_range(args.front, "front")
        body_range = parse_range(args.body, "body")
        back_range = parse_range(args.back, "back")
        front_range = [index for index in front_range if index not in discarded]
        body_range = [index for index in body_range if index not in discarded]
        back_range = [index for index in back_range if index not in discarded]
        if not body_range:
            raise RuntimeError("body 范围不得为空。")
        order = front_range + body_range + back_range
        if order != kept_indexes:
            raise RuntimeError(
                "front、body、back 必须完整覆盖未舍去的暂存页并保持顺序。"
            )
        front_modules = resolve_modules("front", len(front_range), args.front_modules, args.front_names)
        back_modules = resolve_modules("back", len(back_range), args.back_modules, args.back_names)

        stage.mkdir()
        image_names: list[str] = []
        front_names: list[str] = []
        back_names: list[str] = []
        body_count = len(body_range)
        module_pages: dict[str, list[str]] = {module["name"]: [] for module in front_modules + back_modules}
        for section, section_range, modules in (
            ("front", front_range, front_modules),
            ("body", body_range, []),
            ("back", back_range, back_modules),
        ):
            width = max(3, len(str(len(section_range))))
            for section_page, source_index in enumerate(section_range, 1):
                identifier = f"{section if section != 'body' else 'pages'}-{section_page:0{width}d}"
                image_name = f"{identifier}.png"
                os.link(paths[source_index - 1], stage / image_name)
                image_names.append(image_name)
                if section == "front":
                    module_name, _ = module_for_page(modules, section_page)
                    module_pages[module_name].append(identifier)
                    if module_name not in front_names:
                        front_names.append(module_name)
                elif section == "back":
                    module_name, _ = module_for_page(modules, section_page)
                    module_pages[module_name].append(identifier)
                    if module_name not in back_names:
                        back_names.append(module_name)

        writes: dict[Path, str] = {}
        for module_name in front_names:
            writes[latex / "front" / f"{module_name}.tex"] = module_stub(
                module_name, module_pages[module_name]
            )
        for module_name in back_names:
            writes[latex / "back" / f"{module_name}.tex"] = module_stub(
                module_name, module_pages[module_name]
            )
        for index in range(1, body_count + 1):
            identifier = f"pages-{index:03d}"
            writes[latex / "pages" / f"{identifier}.tex"] = page_stub(identifier)

        block = import_block(front_names, body_count, back_names)
        legacy_block_lines = [
            MAIN_BEGIN,
            "% 前后置逐条导入；正文使用类文件的范围命令。",
            *[f"\\input{{front/{name}}}" for name in front_names],
        ]
        if body_count:
            legacy_block_lines.append(f"\\bookinput{{1}}{{{body_count}}}")
        legacy_block_lines.extend(f"\\input{{back/{name}}}" for name in back_names)
        legacy_block_lines.append(MAIN_END)
        legacy_block = "\n".join(legacy_block_lines)
        main_path = latex / "main.tex"
        if main_path.exists():
            if main_path.is_symlink():
                raise RuntimeError(f"拒绝覆盖符号链接: {main_path}")
            current = read_text(main_path)
            if MAIN_BEGIN not in current or MAIN_END not in current:
                raise RuntimeError("已有 main.tex 没有完整生成入口标记，拒绝覆盖。")
            writes[main_path] = replace_import_block(current, block, legacy_block)
        else:
            writes[main_path] = main_template(args.class_name, block)

        for path, content in writes.items():
            if path.is_symlink():
                raise RuntimeError(f"拒绝覆盖符号链接: {path}")
            if path.exists() and not is_stub(read_text(path)) and path.name != "main.tex":
                raise RuntimeError(f"已有内容文件不是生成骨架，拒绝覆盖: {path}")
            originals[path] = path.read_bytes() if path.exists() else None
        stale_body_files = [
            path
            for path in (latex / "pages").glob("pages-*.tex")
            if BODY_TEX_NAME.fullmatch(path.name) and path not in writes
        ]
        for path in stale_body_files:
            if path.is_symlink():
                raise RuntimeError(f"拒绝删除符号链接: {path}")
            if not path.is_file():
                raise RuntimeError(f"旧正文路径不是普通文件，拒绝删除: {path}")
            if not is_stub(read_text(path)):
                raise RuntimeError(f"旧正文文件含有人工作品，拒绝删除: {path}")
            originals[path] = path.read_bytes()
            path.unlink()

        # A changed page classification may make a generated semantic module
        # obsolete. Remove only files that still carry the generator marker;
        # refuse to guess when a human has already filled an old module.
        generated_module_paths = {
            latex / "front" / f"{name}.tex" for name in front_names
        } | {latex / "back" / f"{name}.tex" for name in back_names}
        for directory in (latex / "front", latex / "back"):
            for path in directory.glob("*.tex"):
                if path in generated_module_paths:
                    continue
                if path.is_symlink():
                    raise RuntimeError(f"拒绝处理符号链接: {path}")
                if not path.is_file():
                    raise RuntimeError(f"旧语义模块不是普通文件，拒绝删除: {path}")
                if not is_stub(read_text(path)):
                    raise RuntimeError(
                        f"旧语义模块包含人工内容，拒绝删除；请先人工处理: {path}"
                    )
                originals[path] = path.read_bytes()
                path.unlink()
        for path, content in writes.items():
            write_atomic(path, content)
        installed_images = install_images(control, stage, image_names)
        shutil.rmtree(pages_dir)
        stage.rmdir()
    except Exception as exc:
        try:
            restore_files(originals)
        except Exception as restore_exc:
            print(f"警告：回滚生成文件失败: {type(restore_exc).__name__}: {restore_exc}", file=sys.stderr)
        for path in installed_images:
            if path.exists() and path.is_file():
                path.unlink()
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        print(f"最终页面命名失败，未完成清理: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(
        f"已生成最终页面 {len(image_names)} 张，正文 {body_count} 页；"
        f"舍去暂存页 {len(discarded)} 张。"
    )
    print("前置/后置使用逐条 input，正文使用 bookinput；暂存页已清理。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
