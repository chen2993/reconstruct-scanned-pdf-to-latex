#!/usr/bin/env python3
"""MinerU 环境体检与一次性安装，让执行单元不必自己摸索。

默认行为是**只读体检**（``--status``）：报告本机能不能用 MinerU、用的是哪一份、
版本多少、模型在不在、Python 是否在支持范围内，并在缺失时打印下一条该执行的命令。
安装与模型下载都必须显式触发，绝不会因为跑了一次体检就悄悄下载几个 GB。

用法::

    python -X utf8 scripts/setup_mineru.py --status            # 默认
    python -X utf8 scripts/setup_mineru.py --status --json
    python -X utf8 scripts/setup_mineru.py --locate            # 只打印路径
    python -X utf8 scripts/setup_mineru.py --check-contract
    python -X utf8 scripts/setup_mineru.py --write-config      # 写入项目指针
    python -X utf8 scripts/setup_mineru.py --install           # 显式安装（创建 venv）
    python -X utf8 scripts/setup_mineru.py --download-models   # 约 2 GB，全机共用

``--install`` 与 ``--download-models`` 会访问网络，因此必须显式传入。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mineru_env  # noqa: E402


MINERU_SPEC = "mineru>=4.0,<5"


class SetupError(RuntimeError):
    """体检或安装过程中出现的可读错误。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MinerU 环境体检与一次性安装（默认只读）。"
    )
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        default=Path("."),
        help="重建项目根目录（用于读写项目级指针；缺省为当前目录）",
    )
    parser.add_argument("--mineru-exe", help="显式指定 MinerU 可执行文件")
    parser.add_argument("--status", action="store_true", help="只读体检（默认动作）")
    parser.add_argument("--locate", action="store_true", help="只打印解析到的可执行文件路径")
    parser.add_argument("--check-contract", action="store_true", help="校验 CLI 参数契约")
    parser.add_argument("--write-config", action="store_true", help="把解析结果写入项目配置")
    parser.add_argument("--install", action="store_true", help="创建虚拟环境并安装 MinerU")
    parser.add_argument("--download-models", action="store_true", help="下载模型权重")
    parser.add_argument("--venv", type=Path, help="虚拟环境目录（默认 ~/.mineru-venv）")
    parser.add_argument("--python", dest="python_exe", help="用于创建虚拟环境的解释器")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出体检结果")
    return parser.parse_args()


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def build_report(project: Path, explicit: str | None, environ: dict[str, str]) -> dict[str, object]:
    resolution = mineru_env.resolve(project, explicit=explicit, environ=environ)
    models = mineru_env.model_dir(environ)
    model_bytes = mineru_env.directory_size(models) if models.is_dir() else 0
    report: dict[str, object] = {
        "schema": "mineru-status.v1",
        "project": str(project),
        "python": {"current": "%d.%d.%d" % sys.version_info[:3]},
        "models": {
            "directory": str(models),
            "exists": models.is_dir(),
            "bytes": model_bytes,
            "human": human_bytes(model_bytes),
        },
        "attempts": [candidate.as_dict() for candidate in resolution.attempts],
        "resolved": None,
        "usable": False,
    }

    candidate = resolution.candidate
    if candidate is not None:
        version = mineru_env.version_of(candidate.path)
        python = mineru_env.sibling_python(candidate.path)
        python_used = python or Path(sys.executable)
        python_version = mineru_env.python_version(python_used) if python else "%d.%d.%d" % sys.version_info[:3]
        report["resolved"] = {
            "source": candidate.source,
            "path": str(candidate.path),
            "version": version,
            "python": {
                "path": str(python) if python else None,
                "version": python_version,
                "in_range": mineru_env.version_in_range(python_version),
            },
        }
        report["usable"] = True
    return report


def print_status(report: dict[str, object]) -> None:
    resolved = report.get("resolved")
    print("MinerU 体检")
    print(f"  项目: {report['project']}")
    if isinstance(resolved, dict):
        print(f"  可执行文件: {resolved['path']}")
        print(f"  来源: {resolved['source']}    版本: {resolved['version'] or '未知'}")
        python = resolved.get("python") or {}
        in_range = python.get("in_range")
        flag = "在支持范围内" if in_range else ("不在支持范围内" if in_range is False else "无法判断")
        print(f"  Python: {python.get('version') or '未知'}（{flag}）")
    else:
        print("  可执行文件: 未找到")
        attempts = report.get("attempts") or []
        for item in attempts:
            if not item.get("exists"):
                print(f"  - 未命中 {item['source']}: {item['path']} {item.get('detail') or ''}".rstrip())
    models = report["models"]
    state = "已就位" if models["exists"] and models["bytes"] else "尚未下载"
    print(f"  模型: {models['directory']}（{state}，{models['human']}）")

    if report.get("usable"):
        contract = report.get("contract")
        if isinstance(contract, dict) and contract.get("verified") is False:
            print("  契约: 不匹配——当前 CLI 与适配器不一致，请更新 MinerU 或改用只读探针")
        return
    print()
    print("下一步:")
    print("  python -X utf8 scripts/setup_mineru.py --install")
    print("  python -X utf8 scripts/setup_mineru.py --download-models")


def do_install(args: argparse.Namespace) -> int:
    venv = (args.venv or mineru_env.default_venv()).expanduser()
    interpreter = args.python_exe or sys.executable
    print("将执行以下操作（需要网络）:")
    print(f"  1. 创建虚拟环境: {venv}")
    print(f"  2. 安装: {MINERU_SPEC}")
    print("模型不在此步下载；装完请运行 --download-models。")
    if venv.exists():
        print(f"注意: {venv} 已存在，将复用它并只更新依赖。")
    else:
        created = subprocess.run([interpreter, "-m", "venv", str(venv)], check=False)
        if created.returncode != 0:
            print("创建虚拟环境失败；请确认解释器可用，或用 --python 指定。", file=sys.stderr)
            return 1
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print(f"虚拟环境里没有找到 python: {python}", file=sys.stderr)
        return 1
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", "-U", MINERU_SPEC],
        check=False,
    )
    if installed.returncode != 0:
        print("安装失败；可改用 uv 或检查网络与 Python 版本（需要 3.10–3.14）。", file=sys.stderr)
        return 1
    executable = venv / (
        "Scripts/mineru.exe" if os.name == "nt" else "bin/mineru"
    )
    if not executable.is_file():
        print(f"安装完成但没有找到 {executable}；请检查包版本。", file=sys.stderr)
        return 1
    mineru_env.write_config(
        args.project.resolve(),
        executable,
        version=mineru_env.version_of(executable),
        python=python,
        resolved_at=_today(),
    )
    print(f"已安装并写入项目配置: {executable}")
    print("下一步: python -X utf8 scripts/setup_mineru.py --download-models")
    return 0


def do_download_models(args: argparse.Namespace) -> int:
    candidate = mineru_env.locate_or_raise(args.project.resolve(), explicit=args.mineru_exe)
    venv_root = candidate.path.parent.parent
    downloader = venv_root / (
        "Scripts/mineru-models-download.exe" if os.name == "nt" else "bin/mineru-models-download"
    )
    if not downloader.is_file():
        downloader = venv_root / ("Scripts/mineru.exe" if os.name == "nt" else "bin/mineru")
        command = [str(downloader), "models", "download"]
    else:
        command = [str(downloader)]
    print("将下载 MinerU 模型（约 2 GB，缓存到 "
          f"{mineru_env.model_dir()}，所有项目共用）。")
    print("命令: " + " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print(
            "模型下载未成功；可改用 MINERU_MODEL_SOURCE=modelscope 或手动放置模型。",
            file=sys.stderr,
        )
        return result.returncode
    return 0


def _today() -> str:
    import datetime

    return datetime.date.today().isoformat()


def looks_like_skill_repo(project: Path) -> bool:
    """技能仓库自己不是重建项目；误写会污染版本库。

    判据是"技能仓库的特征文件"而不是"有没有控制目录"：重建项目里
    ``scripts/`` 也存在，但只有技能仓库同时具备 ``SKILL.md`` 与
    ``references/practice`` 这类只属于技能本身的目录。
    """

    return (project / "SKILL.md").is_file() and (project / "references" / "practice").is_dir()


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    environ = dict(os.environ)

    # 显式动作优先；--status 是默认动作，因此单独给出时会覆盖它。
    explicit_actions = [
        name
        for name, enabled in (
            ("locate", args.locate),
            ("install", args.install),
            ("download_models", args.download_models),
            ("write_config", args.write_config),
        )
        if enabled
    ]
    if len(explicit_actions) > 1:
        print(
            "一次只能执行一个动作，收到: " + ", ".join(explicit_actions),
            file=sys.stderr,
        )
        return 2

    try:
        if args.locate:
            candidate = mineru_env.locate_or_raise(project, explicit=args.mineru_exe)
            print(candidate.path)
            return 0
        if args.install:
            return do_install(args)
        if args.download_models:
            return do_download_models(args)
        if args.write_config:
            if looks_like_skill_repo(project):
                print(
                    "拒绝在技能仓库里写项目配置：给具体的重建项目目录传路径，"
                    "例如 `python -X utf8 scripts/setup_mineru.py <project> --write-config`。",
                    file=sys.stderr,
                )
                return 2
            candidate = mineru_env.locate_or_raise(project, explicit=args.mineru_exe)
            python = mineru_env.sibling_python(candidate.path)
            path = mineru_env.write_config(
                project,
                candidate.path,
                version=mineru_env.version_of(candidate.path),
                python=python,
                resolved_at=_today(),
            )
            print(f"已写入 {path}")
            return 0

        report = build_report(project, args.mineru_exe, environ)
        if args.check_contract and report.get("resolved"):
            resolved = report["resolved"]
            report["contract"] = mineru_env.check_contract(Path(resolved["path"]))
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_status(report)
        contract = report.get("contract")
        if isinstance(contract, dict) and contract.get("verified") is False:
            return 1
        return 0 if report.get("usable") else 1
    except mineru_env.MineruEnvError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
