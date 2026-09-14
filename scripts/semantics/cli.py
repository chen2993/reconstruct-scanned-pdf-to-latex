"""语义审计的命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .models import ConfigurationError
from .sources import audit_project, select_report_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="审计 latex/front、latex/pages 和 latex/back 的语义所有权；不读取 PDF 或页图。"
    )
    parser.add_argument("project", type=Path, help="重建项目根目录")
    parser.add_argument(
        "--files",
        nargs="+",
        type=Path,
        metavar="PAGE",
        help="只报告这些逐页文件的问题；可使用绝对路径或项目根目录的相对路径",
    )
    parser.add_argument(
        "--json", action="store_true", help="输出一份机器可读的 JSON 报告"
    )
    return parser.parse_args()


def emit_error(project: Path, message: str, json_output: bool) -> None:
    if json_output:
        print(
            json.dumps(
                {
                    "ok": False,
                    "project": str(project),
                    "files_audited": 0,
                    "issues": [],
                    "error": {"code": "configuration_error", "message": message},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"语义审计配置错误: {message}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        emit_error(project, f"项目目录不存在: {project}", args.json)
        return 2
    try:
        config, config_path = load_config(project)
        pages, issues = audit_project(project, config)
        selected = select_report_files(project, pages, args.files)
        issues = [issue for issue in issues if issue.path in selected]
    except ConfigurationError as exc:
        emit_error(project, str(exc), args.json)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not issues,
                    "project": str(project),
                    "configuration": str(config_path) if config_path else None,
                    "files_audited": len(selected),
                    "files_scanned_for_context": len(pages),
                    "issues": [issue.as_dict() for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif issues:
        for issue in issues:
            print(
                f"{issue.path}:{issue.line}:{issue.column}: "
                f"{issue.code}: {issue.message}"
            )
        print(f"语义审计未通过：{len(selected)} 个文件中发现 {len(issues)} 个问题")
    else:
        suffix = f"；配置 {config_path}" if config_path else ""
        print(f"语义审计通过：{len(selected)} 个文件{suffix}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
