"""候选提取器运行器的路径、页范围与上下文边界测试。"""

from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS


RUNNER = SCRIPTS / "run_optional_extractor.py"


def load_runner_module():
    """Load the manifest helper without executing the CLI entry point."""

    spec = importlib.util.spec_from_file_location("optional_extractor_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put_marker_shim(path, *, help_text, payload=None):
    """Create a deterministic Windows CLI shim for contract/runtime tests."""

    payload_line = ""
    if payload is not None:
        payload_line = f"echo {payload}>candidate.json\r\n"
    path.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"--help\" (\r\n"
        f"  echo {help_text}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%2\"==\"--help\" (\r\n"
        f"  echo {help_text}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        + payload_line
        + "exit /b 0\r\n",
        encoding="utf-8",
    )


def test_runner_requires_explicit_page_range_or_all_pages(tmp_path):
    project = tmp_path / "project"
    (project / "tmp" / "tool-probes").mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    output = project / "tmp" / "tool-probes" / "mineru"
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "mineru",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 2
    assert "--pages" in result.stderr


def test_runner_rejects_output_outside_probe_directory(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "docling",
            "--pages",
            "1-2",
            "--output",
            str(project / "latex" / "bad"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 2
    assert "tmp/tool-probes" in result.stderr


def test_runner_can_write_small_dry_run_manifest_without_tool_output(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "marker"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    # The dry-run still needs a discovered executable.  A tiny local shim keeps
    # this test deterministic without installing Marker in the test environment.
    shim = tmp_path / "marker_single.cmd"
    shim.write_text("@echo off\r\n", encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "marker",
            "--pages",
            "12-14,18",
            "--output",
            str(output),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "optional-extractor-run.v2"
    assert manifest["pages"] == "12,13,14,18"
    assert manifest["candidate_only"] is True
    assert manifest["accepted_as_final_source"] is False
    assert manifest["cli_contract"] == {"verified": False, "reason": "dry-run"}
    assert manifest["output_limits"]["max_total_bytes"] == 128 * 1024 * 1024
    assert "--page_range" in manifest["command"]
    assert "11-13,17" in manifest["command"]


def test_runner_uses_page_scoped_mineru_adapter(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "mineru"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    shim = tmp_path / "mineru.cmd"
    shim.write_text("@echo off\r\n", encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "mineru",
            "--pages",
            "12-14,18",
            "--output",
            str(output),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    command = manifest["command"]
    assert command[1:3] == ["parse", str(source)]
    assert "--pages" in command
    assert "12-14,18" in command
    assert "--json" in command
    assert "-o" not in command


MINERU_SHIM_HELP = "--pages --json --limit --output"


def put_mineru_shim(path, *, version="mineru 4.0.10"):
    """MinerU 垫片：既能回答 --version，也能回答 parse --help。"""

    path.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"--version\" (\r\n"
        f"  echo {version}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%2\"==\"--help\" (\r\n"
        f"  echo {MINERU_SHIM_HELP}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    return path


def test_runner_finds_mineru_from_project_config(tmp_path):
    """配置指针必须能让运行器找到不在 PATH 上的 MinerU。"""

    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "mineru"
    output.mkdir(parents=True)
    control = project / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    shim = put_mineru_shim(tmp_path / "mineru.cmd")
    (control / "mineru-env.json").write_text(
        json.dumps({"schema": "mineru-env.v1", "executable": str(shim)}),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PATH"] = str(tmp_path / "empty")
    env.pop("MINERU_EXE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "mineru",
            "--pages",
            "2",
            "--output",
            str(output),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    resolved = manifest["mineru_executable"]
    assert resolved["source"] == "project-config"
    assert Path(resolved["path"]) == shim
    assert resolved["version"] == "4.0.10"


def test_runner_honours_explicit_mineru_exe(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "mineru"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    shim = put_mineru_shim(tmp_path / "explicit.cmd")

    env = dict(os.environ)
    env["PATH"] = str(tmp_path / "empty")
    env.pop("MINERU_EXE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "mineru",
            "--pages",
            "3",
            "--output",
            str(output),
            "--mineru-exe",
            str(shim),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mineru_executable"]["source"] == "explicit"
    assert Path(manifest["mineru_executable"]["path"]) == shim


def test_runner_missing_mineru_points_at_setup_script(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "mineru"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    env = dict(os.environ)
    env["PATH"] = str(tmp_path / "empty")
    env.pop("MINERU_EXE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "mineru",
            "--pages",
            "2",
            "--output",
            str(output),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode != 0
    assert "setup_mineru.py" in result.stderr
    assert "--install" in result.stderr

def test_runner_prefers_stateless_mineru_kit(tmp_path):
    """同目录存在 mineru-kit 时必须优先用它：mineru parse 需要常驻服务。"""

    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "mineru"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    put_mineru_shim(tmp_path / "mineru.cmd")
    kit = tmp_path / "mineru-kit.cmd"
    kit.write_text(
        "@echo off\r\n"
        "if \"%2\"==\"--help\" (\r\n"
        f"  echo {MINERU_SHIM_HELP}\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PATH"] = str(tmp_path / "empty")
    env.pop("MINERU_EXE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "mineru",
            "--pages",
            "5-6",
            "--output",
            str(output),
            "--mineru-exe",
            str(tmp_path / "mineru.cmd"),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mineru_executable"]["entrypoint"] == "mineru-kit"
    assert Path(manifest["mineru_executable"]["path"]).name == "mineru-kit.cmd"
    command = manifest["command"]
    assert "parse" in command
    assert "--format" in command
    assert "--output" in command
    assert "5-6" in command


def test_runner_warns_when_only_service_entrypoint_exists(tmp_path):
    """只有 mineru（服务客户端）时仍能出计划，但必须留下 warning。"""

    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "mineru"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    shim = tmp_path / "mineru.cmd"
    put_mineru_shim(shim)

    env = dict(os.environ)
    env["PATH"] = str(tmp_path / "empty")
    env.pop("MINERU_EXE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "mineru",
            "--pages",
            "1",
            "--output",
            str(output),
            "--mineru-exe",
            str(shim),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mineru_executable"]["entrypoint"] == "mineru"
    assert "server start" in manifest["mineru_executable"]["warning"]

def test_docling_rejects_non_contiguous_pages(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "docling"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    shim = tmp_path / "docling.cmd"
    shim.write_text("@echo off\r\n", encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "docling",
            "--pages",
            "1,4",
            "--output",
            str(output),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 2
    assert "连续页范围" in result.stderr


def test_docling_uses_explicit_convert_subcommand(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "docling"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    shim = tmp_path / "docling.cmd"
    shim.write_text("@echo off\r\n", encoding="utf-8")
    import os

    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "docling",
            "--pages",
            "1-2",
            "--output",
            str(output),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    command = manifest["command"]
    assert command[1:3] == ["convert", str(source)]
    assert "--page-range" in command


def test_real_run_verifies_cli_and_records_candidate_outputs(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "marker"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    put_marker_shim(
        tmp_path / "marker_single.cmd",
        help_text="--page_range --output_format --output_dir",
        payload="candidate",
    )
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "marker",
            "--pages",
            "2",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert manifest["cli_contract"]["verified"] is True
    assert manifest["output_summary"]["violates_limits"] is False
    assert manifest["output_summary"]["total_bytes_exceeded"] is False
    assert manifest["output_summary"]["oversized_file_count"] == 0
    assert manifest["termination_reason"] is None
    assert any(item["path"] == "candidate.json" for item in manifest["outputs"])


def test_real_run_rejects_a_cli_that_fails_the_help_contract(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "marker"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    put_marker_shim(tmp_path / "marker_single.cmd", help_text="only --help")
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "marker",
            "--pages",
            "2",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 2
    assert "CLI 与当前适配器不匹配" in result.stderr
    assert not (output / "manifest.json").exists()


def test_real_run_marks_oversized_candidate_instead_of_releasing_it(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "marker"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    put_marker_shim(
        tmp_path / "marker_single.cmd",
        help_text="--page_range --output_format --output_dir",
        payload="0123456789abcdef",
    )
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "marker",
            "--pages",
            "2",
            "--output",
            str(output),
            "--max-output-bytes",
            "4",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 1
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "oversize"
    assert manifest["output_summary"]["violates_limits"] is True
    assert manifest["output_summary"]["total_bytes_exceeded"] is False
    assert manifest["output_summary"]["oversized_file_count"] == 1
    assert manifest["output_summary"]["oversized_report_truncated"] is False
    assert manifest["output_summary"]["oversized_files"] == [
        {"path": "candidate.json", "bytes": 18}
    ]


def test_real_run_marks_total_byte_limit_separately_from_file_limit(tmp_path):
    project = tmp_path / "project"
    output = project / "tmp" / "tool-probes" / "marker"
    output.mkdir(parents=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    put_marker_shim(
        tmp_path / "marker_single.cmd",
        help_text="--page_range --output_format --output_dir",
        payload="0123456789",
    )
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            str(project),
            str(source),
            "--tool",
            "marker",
            "--pages",
            "2",
            "--output",
            str(output),
            "--max-output-total-bytes",
            "4",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 1, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["output_summary"]
    assert manifest["status"] == "oversize"
    assert summary["total_bytes"] > 4
    assert summary["max_total_bytes"] == 4
    assert summary["total_bytes_exceeded"] is True
    assert summary["oversized_file_count"] == 0
    assert summary["oversized_files"] == []


def test_manifest_counts_runner_logs_in_total_bytes(tmp_path):
    runner = load_runner_module()
    root = tmp_path / "candidate"
    root.mkdir()
    (root / "candidate.json").write_bytes(b"xx")
    (root / "run.stdout.log").write_bytes(b"0123456789")

    files, summary = runner.file_manifest(
        root,
        max_output_bytes=32,
        max_output_files=256,
        max_output_total_bytes=10,
    )

    assert [item["path"] for item in files] == ["candidate.json"]
    assert summary["file_count"] == 1
    assert summary["candidate_total_bytes"] == 2
    assert summary["log_bytes"] == 10
    assert summary["total_bytes"] == 12
    assert summary["total_bytes_exceeded"] is True
    assert summary["violates_limits"] is True


def test_manifest_caps_oversized_file_report(tmp_path):
    runner = load_runner_module()
    root = tmp_path / "candidate"
    root.mkdir()
    for index in range(70):
        (root / f"page-{index:03d}.bin").write_bytes(b"xx")

    files, summary = runner.file_manifest(
        root,
        max_output_bytes=1,
        max_output_files=256,
        max_output_total_bytes=10_000,
    )

    assert len(files) == 70
    assert summary["file_count"] == 70
    assert summary["oversized_file_count"] == 70
    assert len(summary["oversized_files"]) == 64
    assert summary["oversized_report_truncated"] is True
    assert summary["total_bytes_exceeded"] is False
    assert summary["violates_limits"] is True
