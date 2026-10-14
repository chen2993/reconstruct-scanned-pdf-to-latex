"""可选工具探针必须只读、可重复运行，并在工具缺失时正常返回。"""

from __future__ import annotations

import json
import subprocess
import sys

from conftest import SCRIPTS


def test_optional_tool_probe_is_json_and_does_not_need_pdf(tmp_path):
    output = tmp_path / "probe.json"
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(SCRIPTS / "probe_optional_tools.py"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "optional-tool-probe.v2"
    assert payload["read_pdf"] is False
    assert payload["ran_conversion"] is False
    assert {
        "mineru",
        "marker",
        "docling",
        "nougat",
        "surya",
        "pdf_extract_kit",
        "formula_helper",
    } <= set(payload["tools"])
    assert payload["tools"]["mineru"]["category"] == "layout-structure-candidate"
    assert payload["tools"]["nougat"]["fit_for_chinese_scans"] == "weak"
    assert payload["tools"]["surya"]["runner_page_index"] == "image-only"
    assert payload["tools"]["pdf_extract_kit"]["commands"] == []

