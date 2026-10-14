"""MinerU 环境体检、发现顺序与项目配置的测试。

全部用 ``.cmd`` 垫片与 ``tmp_path``：既不要求本机真的装了 MinerU，也不联网。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS


SETUP = SCRIPTS / "setup_mineru.py"
RUNNER = SCRIPTS / "run_optional_extractor.py"
CONTROL = ".reconstruct-scanned-pdf-to-latex"

GOOD_HELP = "usage: mineru parse --pages --json --limit --output"


def put_mineru_shim(path: Path, *, help_text: str = GOOD_HELP, version: str = "mineru 4.0.10") -> Path:
    """生成一个可预测的 MinerU 垫片（Windows .cmd）。"""

    path.write_text(
        "@echo off\r\n"
        'if "%1"=="--version" (\r\n'
        f"  echo {version}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        'if "%2"=="--help" (\r\n'
        f"  echo {help_text}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        'if "%1"=="--help" (\r\n'
        f"  echo {help_text}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    return path


def make_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tmp" / "tool-probes").mkdir(parents=True, exist_ok=True)
    (root / CONTROL).mkdir(parents=True, exist_ok=True)
    return root


def run_setup(project: Path, *args: object, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SETUP), str(project), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def status_json(project: Path, *args: object, env: dict[str, str] | None = None) -> dict:
    result = run_setup(project, "--status", "--json", *args, env=env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def write_config(project: Path, executable: Path) -> Path:
    path = project / CONTROL / "mineru-env.json"
    path.write_text(
        json.dumps(
            {
                "schema": "mineru-env.v1",
                "executable": str(executable),
                "version": "4.0.10",
                "python": None,
                "resolved_at": "2026-01-01",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def isolated_env(**overrides: str) -> dict[str, str]:
    """清掉会影响发现顺序的继承变量，避免测试受本机真实环境干扰。"""

    env = dict(os.environ)
    for name in ("MINERU_EXE", "MINERU_HOME", "MINERU_MODEL_BASE_DIR"):
        env.pop(name, None)
    env.update(overrides)
    return env


def test_status_reports_missing_tool_with_actionable_hint(tmp_path):
    project = make_project(tmp_path / "book")
    env = isolated_env(PATH=str(tmp_path / "empty"))
    result = run_setup(project, "--status", env=env)
    assert result.returncode == 1
    assert "--install" in result.stdout
    assert "未找到" in result.stdout


def test_status_json_is_parseable_when_missing(tmp_path):
    project = make_project(tmp_path / "book")
    env = isolated_env(PATH=str(tmp_path / "empty"))
    result = run_setup(project, "--status", "--json", env=env)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["usable"] is False
    assert payload["resolved"] is None
    assert payload["schema"] == "mineru-status.v1"


def test_discovery_precedence_explicit_env_config_path(tmp_path):
    project = make_project(tmp_path / "book")
    explicit = put_mineru_shim(tmp_path / "explicit.cmd")
    from_env = put_mineru_shim(tmp_path / "env.cmd")
    from_config = put_mineru_shim(tmp_path / "config.cmd")
    on_path = tmp_path / "pathdir"
    on_path.mkdir()
    put_mineru_shim(on_path / "mineru.cmd")
    write_config(project, from_config)

    both = isolated_env(MINERU_EXE=str(from_env), PATH=str(on_path))

    # 显式参数压过一切。
    payload = status_json(project, "--mineru-exe", explicit, env=both)
    assert payload["resolved"]["source"] == "explicit"
    assert Path(payload["resolved"]["path"]) == explicit

    # 去掉显式参数后，环境变量压过项目配置与 PATH。
    payload = status_json(project, env=both)
    assert payload["resolved"]["source"] == "env"
    assert Path(payload["resolved"]["path"]) == from_env

    # 再去掉环境变量，项目配置压过 PATH。
    payload = status_json(project, env=isolated_env(PATH=str(on_path)))
    assert payload["resolved"]["source"] == "project-config"
    assert Path(payload["resolved"]["path"]) == from_config

    # 清掉配置后回退到 PATH。
    (project / CONTROL / "mineru-env.json").unlink()
    payload = status_json(project, env=isolated_env(PATH=str(on_path)))
    assert payload["resolved"]["source"] == "path"
    assert Path(payload["resolved"]["path"]) == on_path / "mineru.cmd"


def test_locate_prints_only_the_path(tmp_path):
    project = make_project(tmp_path / "book")
    shim = put_mineru_shim(tmp_path / "mineru.cmd")
    result = run_setup(project, "--mineru-exe", shim, "--locate", env=isolated_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(shim)
    assert result.stderr.strip() == ""


def test_locate_fails_for_missing_explicit_path(tmp_path):
    project = make_project(tmp_path / "book")
    result = run_setup(
        project, "--mineru-exe", tmp_path / "nope.cmd", "--locate", env=isolated_env()
    )
    assert result.returncode != 0
    assert "不存在" in result.stderr


def test_check_contract_rejects_incompatible_cli(tmp_path):
    project = make_project(tmp_path / "book")
    shim = put_mineru_shim(tmp_path / "mineru.cmd", help_text="usage: mineru parse --pages")
    result = run_setup(
        project, "--mineru-exe", shim, "--status", "--check-contract", "--json", env=isolated_env()
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["contract"]["verified"] is False
    assert sorted(payload["contract"]["missing_tokens"]) == ["--json", "--limit", "--output"]


def test_check_contract_accepts_matching_cli(tmp_path):
    project = make_project(tmp_path / "book")
    shim = put_mineru_shim(tmp_path / "mineru.cmd")
    result = run_setup(
        project, "--mineru-exe", shim, "--status", "--check-contract", "--json", env=isolated_env()
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["contract"]["verified"] is True
    assert payload["contract"]["missing_tokens"] == []


def test_write_config_writes_documented_schema(tmp_path):
    project = make_project(tmp_path / "book")
    shim = put_mineru_shim(tmp_path / "mineru.cmd")
    result = run_setup(project, "--mineru-exe", shim, "--write-config", env=isolated_env())
    assert result.returncode == 0, result.stderr
    payload = json.loads((project / CONTROL / "mineru-env.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "mineru-env.v1"
    assert payload["executable"] == str(shim)
    assert payload["version"] == "4.0.10"
    assert set(payload) == {"schema", "executable", "version", "python", "resolved_at"}
    # 不能留下半成品：临时文件必须已被替换掉。
    leftovers = list((project / CONTROL).glob(".mineru-env.json.stage-*"))
    assert leftovers == []


def test_write_config_refuses_skill_repo(tmp_path):
    """技能仓库不是重建项目，不能把项目配置写进版本库。"""

    skill_like = tmp_path / "skillrepo"
    (skill_like / "references" / "practice").mkdir(parents=True)
    (skill_like / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    shim = put_mineru_shim(tmp_path / "mineru.cmd")

    result = run_setup(skill_like, "--mineru-exe", shim, "--write-config", env=isolated_env())
    assert result.returncode == 2
    assert "拒绝" in result.stderr
    assert not (skill_like / CONTROL / "mineru-env.json").exists()

def test_write_config_failure_leaves_no_partial_file(tmp_path, monkeypatch):
    """写入失败时不能留下半截配置。"""

    import importlib.util

    spec = importlib.util.spec_from_file_location("mineru_env_under_test", SCRIPTS / "mineru_env.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # 注册进 sys.modules：dataclasses 解析注解时需要能按模块名反查。
    sys.modules["mineru_env_under_test"] = module
    spec.loader.exec_module(module)

    project = make_project(tmp_path / "book")
    target = project / CONTROL / "mineru-env.json"
    original = module.os.replace

    def explode(source, destination):
        raise OSError("disk full")

    monkeypatch.setattr(module.os, "replace", explode)
    try:
        module.write_config(project, tmp_path / "mineru.cmd", version="4.0.10")
    except OSError:
        pass
    finally:
        monkeypatch.setattr(module.os, "replace", original)
    assert not target.exists()
    assert list((project / CONTROL).glob(".mineru-env.json.stage-*")) == []
