"""确定性链路端到端：init → split → correct → renumber → orchestrate → checkpoint。

这些脚本之间靠文件契约相连（目录名、清单状态、生成骨架、白名单），单独测一个
模块测不出跨脚本的断裂。这里在临时目录里跑完整链路，并断言每一步留下的产物。
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS = REPO / "scripts"

pytest.importorskip("fitz", reason="需要 PyMuPDF 生成测试扫描件")
pytest.importorskip("PIL", reason="需要 Pillow 生成测试扫描件")

PAGE_COUNT = 12


def run(*args: object, expect: int = 0) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == expect, (
        f"退出码 {result.returncode} != {expect}: {' '.join(map(str, args))}\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return result


def make_scan(path: Path, pages: int) -> None:
    """An image-only PDF: one embedded full-page raster per page."""

    import fitz
    from PIL import Image, ImageDraw

    width, height = 1240, 1754  # A4 at 150 dpi
    document = fitz.open()
    for index in range(1, pages + 1):
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle([60, 60, width - 60, height - 60], outline="black", width=3)
        for line in range(12):
            draw.line([120, 260 + line * 60, width - 140, 260 + line * 60], fill="gray", width=6)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        page = document.new_page(width=width * 72 / 150, height=height * 72 / 150)
        page.insert_image(page.rect, stream=buffer.getvalue())
    document.save(path)
    document.close()


@dataclass
class Pipeline:
    """A bootstrapped project that has already been split and renamed."""

    root: Path
    skill: Path
    # 拆分清单在重编号后会被清理，因此在链路上捕获一份供断言使用。
    split_manifest: dict

    @property
    def control(self) -> Path:
        return self.root / ".reconstruct-scanned-pdf-to-latex"

    @property
    def scripts(self) -> Path:
        return self.root / "scripts"


@pytest.fixture
def pipeline(tmp_path: Path) -> Pipeline:
    # 复制技能本体，模拟真实部署：项目自带工具链，而不是引用技能目录。
    skill = tmp_path / "skill"
    shutil.copytree(
        REPO, skill,
        ignore=shutil.ignore_patterns(".git", "tmp", "__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    scripts = skill / "scripts"
    scan = tmp_path / "scan.pdf"
    make_scan(scan, PAGE_COUNT)

    project = tmp_path / "book"
    run(scripts / "init_project.py", project, "--git")
    run(scripts / "split_pdf.py", project, scan, "--image-source", "auto", "--dpi", "300")
    split_manifest = json.loads(
        (project / ".reconstruct-scanned-pdf-to-latex" / "extracted" / "manifest.json").read_text(encoding="utf-8")
    )
    run(scripts / "correct_pages.py", project)
    corrected = json.loads(
        (project / ".reconstruct-scanned-pdf-to-latex" / "extracted" / "manifest.json").read_text(encoding="utf-8")
    )
    assert corrected["state"] == "corrected"
    run(
        scripts / "renumber_pages.py", project,
        "--discard", "2",
        "--front", "1-6",
        "--front-modules", "cover=1,dedication=2,toc=3-4,preface=5",
        "--body", "7-11",
        "--back", "12",
        "--back-modules", "afterword=1",
        "--class-name", "samplebook",
    )
    return Pipeline(project, skill, split_manifest)


def test_split_keeps_embedded_pixels(pipeline):
    manifest = pipeline.split_manifest
    assert manifest["page_count"] == PAGE_COUNT
    assert manifest["page_source_summary"]["embedded_image"] == PAGE_COUNT
    first = manifest["pages"][0]
    assert (first["width_px"], first["height_px"]) == (1240, 1754)
    assert first["resampled"] is False


def test_renumber_clears_the_workspace_and_installs_final_names(pipeline):
    control = pipeline.control
    assert not (control / "extracted").exists()
    assert (control / "front-001.png").is_file()
    assert (control / "pages-005.png").is_file()
    assert (control / "back-001.png").is_file()
    # the discarded page must not survive under any final name
    assert not (control / "front-006.png").exists()


def test_renumber_writes_semantic_modules_not_page_numbered_ones(pipeline):
    front = pipeline.root / "latex" / "front"
    back = pipeline.root / "latex" / "back"
    assert {path.name for path in front.glob("*.tex")} == {
        "cover.tex", "dedication.tex", "toc.tex", "preface.tex",
    }
    assert {path.name for path in back.glob("*.tex")} == {"afterword.tex"}
    assert not list(front.glob("front-*.tex"))
    assert not list(back.glob("back-*.tex"))


def test_renumber_scaffolds_a_toc_module_that_passes_its_audit(pipeline):
    """toc.tex 必须自带一次自动目录指令，否则第一次构建必然失败。"""

    toc = (pipeline.root / "latex" / "front" / "toc.tex").read_text(encoding="utf-8")
    assert "\\bookmaketoc" in toc
    run(pipeline.scripts / "audit_toc.py", pipeline.root)


def test_renumber_writes_one_body_range_and_literal_module_inputs(pipeline):
    main = (pipeline.root / "latex" / "main.tex").read_text(encoding="utf-8")
    assert main.count("\\bookinput{1}{5}") == 1
    for name in ("cover", "dedication", "toc", "preface"):
        assert f"\\input{{front/{name}}}" in main
    assert "\\input{back/afterword}" in main
    assert len(list((pipeline.root / "latex" / "pages").glob("pages-*.tex"))) == 5


def test_scaffolded_project_passes_every_static_audit(pipeline):
    for script in ("audit_toc.py", "audit_provenance.py", "audit_semantics.py"):
        run(pipeline.scripts / script, pipeline.root)


def test_dispatch_refuses_stubs_then_accepts_transcribed_pages(pipeline):
    run(pipeline.scripts / "orchestrate.py", pipeline.root, "plan", "--batch", "3")
    run(pipeline.scripts / "orchestrate.py", pipeline.root, "next")
    packet = pipeline.control / "dispatch" / "b001-003.md"
    assert packet.is_file()
    text = packet.read_text(encoding="utf-8")
    assert "停工反馈" in text
    assert "latex/pages/pages-001.tex" in text

    # 骨架阶段必须先被拒绝，否则“已派发”会被误当成“已完成”
    refused = run(pipeline.scripts / "orchestrate.py", pipeline.root, "verify", "b001-003", expect=1)
    assert "仍是占位骨架" in refused.stdout

    for number in range(1, 4):
        (pipeline.root / "latex" / "pages" / f"pages-{number:03d}.tex").write_text(
            f"% Source page: pages-{number:03d}\n"
            "\\begin{bookbody}\n\\begin{booktext}\n正文。\n\\end{booktext}\n\\end{bookbody}\n",
            encoding="utf-8",
        )
    run(pipeline.scripts / "orchestrate.py", pipeline.root, "verify", "b001-003")
    state = json.loads((pipeline.control / "dispatch.json").read_text(encoding="utf-8"))
    assert state["batches"]["b001-003"]["status"] == "verified"


def test_checkpoint_commits_only_the_verified_batch(pipeline):
    (pipeline.root / "unrelated.txt").write_text("must not be committed\n", encoding="utf-8")
    run(pipeline.scripts / "orchestrate.py", pipeline.root, "plan", "--batch", "3")
    for number in range(1, 4):
        (pipeline.root / "latex" / "pages" / f"pages-{number:03d}.tex").write_text(
            f"% Source page: pages-{number:03d}\n"
            "\\begin{bookbody}\n\\begin{booktext}\n正文。\n\\end{booktext}\n\\end{bookbody}\n",
            encoding="utf-8",
        )
    run(pipeline.scripts / "orchestrate.py", pipeline.root, "verify", "b001-003")
    run(pipeline.scripts / "orchestrate.py", pipeline.root, "checkpoint", "b001-003")

    log = subprocess.run(
        ["git", "-C", str(pipeline.root), "log", "-1", "--pretty=%s"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert log.stdout.strip() == "<agent><content> transcribe pages 001-003"
    files = subprocess.run(
        ["git", "-C", str(pipeline.root), "show", "--name-only", "--pretty=", "HEAD"],
        capture_output=True, text=True, encoding="utf-8",
    ).stdout.split()
    assert set(files) == {f"latex/pages/pages-{n:03d}.tex" for n in range(1, 4)}
    assert "unrelated.txt" not in files
