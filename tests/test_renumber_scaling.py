"""重编号在教材量级下的编号与命名契约。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS


def build_workspace(project: Path, pages: int) -> None:
    """Scaffold a project whose extracted workspace has ``pages`` staged pages."""

    for part in ("latex/front", "latex/back", "latex/pages", "docs"):
        (project / part).mkdir(parents=True, exist_ok=True)
    control = project / ".reconstruct-scanned-pdf-to-latex"
    workspace = control / "extracted"
    workspace.mkdir(parents=True, exist_ok=True)
    width = max(3, len(str(pages)))
    records = []
    import hashlib

    for index in range(1, pages + 1):
        name = f"page-{index:0{width}d}.png"
        payload = f"page-{index}".encode()
        (workspace / name).write_bytes(payload)
        records.append(
            {
                "page_index": index,
                "filename": name,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    import json

    (workspace / "manifest.json").write_text(
        json.dumps(
            {"kind": "pdf-pages", "state": "corrected", "pages": records},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (control / "semantic-audit.json").write_text("{}", encoding="utf-8")


def renumber(project: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "renumber_pages.py"), str(project), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


@pytest.mark.parametrize("pages", [999, 1000])
def test_page_number_width_is_consistent_across_the_chain(tmp_path, pages):
    """编号宽度必须被整条链路共同接受。

    正文文件名、来源页标记、语义审计的期望文件名和类文件的 ``\\bookinput``
    各自推导宽度；它们一旦不一致，缺页只会在编译或审计时才暴露。
    """

    project = tmp_path / f"book{pages}"
    project.mkdir()
    build_workspace(project, pages)
    result = renumber(project, "--body", f"1-{pages}", "--front-modules", "none", "--back-modules", "none")
    assert result.returncode == 0, result.stderr

    names = sorted(path.name for path in (project / "latex" / "pages").glob("pages-*.tex"))
    assert len(names) == pages
    assert names[0] == "pages-001.tex"

    # 重编号写入的来源页标记必须与文件名逐字一致
    first = (project / "latex" / "pages" / names[0]).read_text(encoding="utf-8")
    last = (project / "latex" / "pages" / names[-1]).read_text(encoding="utf-8")
    assert f"% Source page: {names[0][:-4]}" in first
    assert f"% Source page: {names[-1][:-4]}" in last

    import json

    (project / ".reconstruct-scanned-pdf-to-latex" / "semantic-audit.json").write_text(
        json.dumps(
            {
                "owner_environments": [],
                "owner_parent_environments": {},
                "cross_page_owner_environments": [],
                "question_owner_environments": [],
                "answer_owner_environments": [],
                "answer_media_environments": [],
            }
        ),
        encoding="utf-8",
    )
    # 审计器按同一条 \bookinput 范围反推文件名；它必须能全部找到
    audit = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "audit_provenance.py"), str(project)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert audit.returncode == 0, audit.stdout + audit.stderr

    semantics = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "audit_semantics.py"), str(project)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert semantics.returncode == 0, semantics.stdout + semantics.stderr

    # 调度器同样按三位最小宽度拼页面标识；任务包里的白名单必须对应真实文件
    orchestrate = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "orchestrate.py"), str(project), "plan", "--batch", "10"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert orchestrate.returncode == 0, orchestrate.stderr
    orchestrate = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "orchestrate.py"), str(project), "next"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert orchestrate.returncode == 0, orchestrate.stderr
    packet = (project / ".reconstruct-scanned-pdf-to-latex" / "dispatch" / "b001-010.md").read_text(
        encoding="utf-8"
    )
    for number in range(1, 11):
        assert f"`latex/pages/pages-{number:03d}.tex`" in packet
    # 最后一个批次必须引用真实存在的文件名，而不是补零到页数宽度
    state = json.loads((project / ".reconstruct-scanned-pdf-to-latex" / "dispatch.json").read_text(encoding="utf-8"))
    last = max(state["batches"], key=lambda key: state["batches"][key]["start"])
    end = state["batches"][last]["end"]
    assert (project / "latex" / "pages" / f"pages-{end:03d}.tex").is_file()
