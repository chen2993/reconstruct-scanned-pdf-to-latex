#!/usr/bin/env python3
"""MinerU 可执行文件的统一发现与配置读写。

为什么单独一个模块：安装脚本（``setup_mineru.py``）和候选运行器
（``run_optional_extractor.py``）必须用**同一套**定位顺序，否则会出现
"体检说找到了、运行器却找不到"这种最难排查的不一致。

发现顺序（自上而下，先命中先用）：

1. 显式参数 ``--mineru-exe PATH``
2. 环境变量 ``MINERU_EXE``
3. 项目配置 ``.reconstruct-scanned-pdf-to-latex/mineru-env.json``
4. ``PATH`` 上的 ``mineru``（``shutil.which``）
5. 常见虚拟环境位置（``~/.mineru-venv``、``$MINERU_HOME/venv``）

``mineru`` 通常装在独立虚拟环境里、不在 PATH 上，所以第 5 步不是可有可无的
兜底：它决定了"装好了但用不上"会不会发生。

模型缓存与虚拟环境是两回事：模型默认落在 ``~/.mineru/models``，由所有项目共用；
虚拟环境只是解释器与包的容器。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from page_workspace import control_dir  # noqa: E402


CONFIG_FILENAME = "mineru-env.json"
CONFIG_SCHEMA = "mineru-env.v1"

# MinerU 4.x 支持与要求的 Python 范围（见其包元数据）。
PYTHON_MIN = (3, 10)
PYTHON_MAX_EXCLUSIVE = (3, 15)

SOURCE_EXPLICIT = "explicit"
SOURCE_ENV = "env"
SOURCE_PROJECT_CONFIG = "project-config"
SOURCE_PATH = "path"
SOURCE_VENV = "venv"
SOURCE_ORDER = (
    SOURCE_EXPLICIT,
    SOURCE_ENV,
    SOURCE_PROJECT_CONFIG,
    SOURCE_PATH,
    SOURCE_VENV,
)

# 安装脚本创建的默认虚拟环境；模型共享，环境各自独立。
DEFAULT_VENV_NAME = ".mineru-venv"

_VERSION_TOKEN = re.compile(r"\d+\.\d+(?:\.\d+)?(?:[-+.\w]*)?")


class MineruEnvError(RuntimeError):
    """发现或配置 MinerU 时出现的可读错误。"""


@dataclass
class Candidate:
    """一个候选可执行文件；``exists`` 为假时表示该来源指向了不存在的路径。"""

    source: str
    path: Path
    exists: bool
    detail: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "path": str(self.path),
            "exists": self.exists,
            "detail": self.detail,
        }


@dataclass
class Resolution:
    """完整解析结果：命中的候选 + 全部尝试过的来源。"""

    candidate: Candidate | None
    attempts: list[Candidate] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.candidate is not None


def config_path(project: Path) -> Path:
    return control_dir(project) / CONFIG_FILENAME


def model_dir(environ: Mapping[str, str] | None = None) -> Path:
    """模型缓存目录：``MINERU_MODEL_BASE_DIR`` > ``MINERU_HOME``/models > ``~/.mineru/models``。"""

    env = os.environ if environ is None else environ
    explicit = env.get("MINERU_MODEL_BASE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    home = env.get("MINERU_HOME")
    if home:
        return Path(home).expanduser() / "models"
    return Path.home() / ".mineru" / "models"


def default_venv(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    home = env.get("MINERU_HOME")
    if home:
        return Path(home).expanduser() / "venv"
    return Path.home() / DEFAULT_VENV_NAME


def _executable_names() -> tuple[str, ...]:
    # Windows 上虚拟环境把入口放在 Scripts/ 并带 .exe；POSIX 在 bin/。
    if os.name == "nt":
        return ("Scripts/mineru.exe", "Scripts/mineru.cmd", "bin/mineru")
    return ("bin/mineru",)


def _python_names() -> tuple[str, ...]:
    if os.name == "nt":
        return ("Scripts/python.exe", "Scripts/python3.exe", "bin/python", "bin/python3")
    return ("bin/python", "bin/python3")


def sibling_python(executable: Path) -> Path | None:
    """取同一个虚拟环境里的 python，用于判断版本是否受支持。"""

    base = executable.parent.parent if executable.parent.name in {"Scripts", "bin"} else executable.parent
    for relative in _python_names():
        candidate = base / relative
        if candidate.is_file():
            return candidate
    return None


def sibling_executable(executable: Path, name: str) -> Path | None:
    """取同一目录下的同名入口（例如 ``mineru`` 旁边的 ``mineru-kit``）。

    安装器总是把同一批 console scripts 放在一起，所以"派生"比再去 PATH 上找一遍
    可靠：它能命中项目配置指向的那个虚拟环境，而不是另一个全局安装。
    """

    candidates = [executable.with_name(name)]
    if os.name == "nt":
        candidates.append(executable.with_name(f"{name}.exe"))
        candidates.append(executable.with_name(f"{name}.cmd"))
    else:
        candidates.append(executable.with_name(f"{name}.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def run_capture(command: list[str], timeout: float = 8.0) -> tuple[int, str] | None:
    """运行一个短命令并合并 stdout/stderr；任何异常都返回 ``None``。"""

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return result.returncode, output


def version_of(executable: Path, timeout: float = 8.0) -> str | None:
    """读取 ``mineru --version`` 并抽出形如 ``4.0.10`` 的版本号。"""

    captured = run_capture([str(executable), "--version"], timeout=timeout)
    if captured is None:
        return None
    _, output = captured
    match = _VERSION_TOKEN.search(output)
    if match:
        return match.group(0)
    return None


def python_version(executable: Path, timeout: float = 8.0) -> str | None:
    captured = run_capture(
        [str(executable), "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
        timeout=timeout,
    )
    if captured is None:
        return None
    returncode, output = captured
    if returncode != 0 or not output:
        return None
    token = output.strip().splitlines()[0].strip()
    return token or None


def version_in_range(version: str | None) -> bool | None:
    """MinerU 4.x 要求 ``>=3.10,<3.15``；无法判断时返回 ``None``。"""

    if not version:
        return None
    parts = version.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None
    return PYTHON_MIN <= (major, minor) < PYTHON_MAX_EXCLUSIVE


def contract_tokens(help_text: str) -> dict[str, bool]:
    """运行器适配器依赖的四个真实参数。"""

    return {
        "--pages": "--pages" in help_text,
        "--json": "--json" in help_text,
        "--limit": "--limit" in help_text,
        "--output": "--output" in help_text,
    }


def check_contract(executable: Path, timeout: float = 10.0) -> dict[str, object]:
    """探测 ``mineru parse --help`` 是否支持当前适配器用到的参数。"""

    command = [str(executable), "parse", "--help"]
    captured = run_capture(command, timeout=timeout)
    if captured is None:
        return {
            "command": command,
            "verified": False,
            "reason": "命令无法运行或超时",
            "tokens": {},
        }
    returncode, output = captured
    tokens = contract_tokens(output)
    missing = sorted(token for token, present in tokens.items() if not present)
    return {
        "command": command,
        "returncode": returncode,
        "verified": returncode == 0 and not missing,
        "missing_tokens": missing,
        "tokens": tokens,
    }


def read_config(project: Path) -> dict[str, object] | None:
    path = config_path(project)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MineruEnvError(f"无法读取 MinerU 配置 {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MineruEnvError(f"MinerU 配置顶层必须是对象: {path}")
    return payload


def write_config(
    project: Path,
    executable: Path,
    *,
    version: str | None = None,
    python: Path | None = None,
    resolved_at: str | None = None,
) -> Path:
    """原子写入项目级指针；配置只是缓存，不是事实来源。"""

    path = config_path(project)
    payload = {
        "schema": CONFIG_SCHEMA,
        "executable": str(executable),
        "version": version,
        "python": str(python) if python else None,
        "resolved_at": resolved_at,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.stage-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _path_candidates(environ: Mapping[str, str]) -> list[Path]:
    found = shutil.which("mineru", path=environ.get("PATH"))
    return [Path(found)] if found else []


def _venv_candidates(environ: Mapping[str, str]) -> list[Path]:
    roots = [default_venv(environ)]
    home = environ.get("MINERU_HOME")
    if home:
        roots.append(Path(home).expanduser() / "venv")
    paths: list[Path] = []
    for root in roots:
        for relative in _executable_names():
            candidate = root / relative
            if candidate not in paths:
                paths.append(candidate)
    return paths


def resolve(
    project: Path | None = None,
    *,
    explicit: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Resolution:
    """按固定顺序解析 MinerU 可执行文件。

    显式参数指向不存在的路径时直接报错——那是调用方明确指定要用的东西，
    静默换成另一个可执行文件比失败更糟。环境变量与项目配置同理只作"提示"：
    指向缺失路径时记录原因并继续往下找。
    """

    env = os.environ if environ is None else environ
    attempts: list[Candidate] = []

    def record(source: str, path: Path | None) -> Candidate | None:
        if path is None:
            return None
        candidate = Candidate(source=source, path=path, exists=path.is_file())
        attempts.append(candidate)
        return candidate if candidate.exists else None

    if explicit is not None:
        candidate = record(SOURCE_EXPLICIT, Path(explicit).expanduser())
        if candidate is None:
            raise MineruEnvError(f"显式指定的 MinerU 不存在或不是文件: {explicit}")
        return Resolution(candidate=candidate, attempts=attempts)

    env_value = env.get("MINERU_EXE")
    if env_value:
        candidate = record(SOURCE_ENV, Path(env_value).expanduser())
        if candidate is not None:
            return Resolution(candidate=candidate, attempts=attempts)

    if project is not None:
        payload = read_config(project)
        if payload is not None:
            configured = payload.get("executable")
            if isinstance(configured, str) and configured.strip():
                candidate = record(SOURCE_PROJECT_CONFIG, Path(configured.strip()).expanduser())
                if candidate is not None:
                    return Resolution(candidate=candidate, attempts=attempts)
            else:
                attempts.append(
                    Candidate(
                        source=SOURCE_PROJECT_CONFIG,
                        path=config_path(project),
                        exists=False,
                        detail="配置里没有可用的 executable 字段",
                    )
                )

    for path in _path_candidates(env):
        candidate = record(SOURCE_PATH, path)
        if candidate is not None:
            return Resolution(candidate=candidate, attempts=attempts)

    for path in _venv_candidates(env):
        candidate = record(SOURCE_VENV, path)
        if candidate is not None:
            return Resolution(candidate=candidate, attempts=attempts)

    return Resolution(candidate=None, attempts=attempts)


def locate_or_raise(
    project: Path | None = None,
    *,
    explicit: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Candidate:
    resolution = resolve(project, explicit=explicit, environ=environ)
    if resolution.candidate is None:
        raise MineruEnvError(
            "未找到可用的 MinerU。先运行 "
            "`python -X utf8 scripts/setup_mineru.py --status` 体检；"
            "未安装时用 `python -X utf8 scripts/setup_mineru.py --install` "
            "创建独立虚拟环境（模型另用 `--download-models`，约 2 GB）。"
        )
    return resolution.candidate


def directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total
