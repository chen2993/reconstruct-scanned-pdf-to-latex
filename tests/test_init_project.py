"""初始化产物必须自洽：项目自带可运行的审计与调度链。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS, plain_page


def init_project(target):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "init_project.py"), str(target)],
        capture_output=True, text=True, encoding="utf-8",
    )


@pytest.fixture
def fresh(tmp_path):
    root = tmp_path / "proj"
    result = init_project(root)
    assert result.returncode == 0, result.stderr
    return root


def test_creates_canonical_workspace(fresh):
    control = fresh / ".reconstruct-scanned-pdf-to-latex"
    assert (control / "extracted").is_dir()
    assert not (control / "extraced").exists()


def test_creates_latex_assets(fresh):
    assert (fresh / "latex" / "assets").is_dir()


def test_copies_toolchain_scripts(fresh):
    # build.ps1 resolves these relative to the project root
    for name in (
        "audit_toc.py",
        "audit_pdf_outline.py",
        "audit_provenance.py",
        "audit_semantics.py",
        "orchestrate.py",
    ):
        assert (fresh / "scripts" / name).is_file(), name
    assert (fresh / "scripts" / "semantics" / "sources.py").is_file()


def test_copies_template(fresh):
    assert (fresh / "template" / "base.cls").is_file()
    assert (fresh / "template" / "build.ps1").is_file()


def test_copied_scripts_are_runnable(fresh):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(fresh / "scripts" / "audit_semantics.py"),
         str(fresh)],
        capture_output=True, text=True, encoding="utf-8",
    )
    # no pages yet, so this reports a configuration error rather than crashing
    assert result.returncode in (0, 1, 2)
    assert "Traceback" not in result.stderr


def test_gitignore_covers_build_artifacts(fresh):
    text = (fresh / ".gitignore").read_text(encoding="utf-8")
    for needle in ("/extracted/", "/tmp/", "/dist/"):
        assert needle in text, needle
    assert "extraced" not in text


def test_refuses_non_empty_target(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    (target / "keep.txt").write_text("x", encoding="utf-8")
    result = init_project(target)
    assert result.returncode == 2
    assert "不为空" in result.stderr
    # nothing was damaged
    assert (target / "keep.txt").read_text(encoding="utf-8") == "x"


def test_semantic_config_is_valid_json(fresh):
    control = fresh / ".reconstruct-scanned-pdf-to-latex"
    payload = json.loads((control / "semantic-audit.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    for name in ("progress.md", "style-cards.md", "page-corrections.json"):
        assert (control / name).is_file(), name
    assert (control / "answer-sentinels.txt").is_file()
    for name in ("style.md", "figures.md", "final.md", "style-gaps.md", "book.md"):
        assert (control / "reviews" / name).is_file(), name


def test_semantics_auditor_runs_on_initialized_project(fresh):
    """The copied auditor must accept a project right after scaffolding."""
    pages = fresh / "latex" / "pages"
    for number in range(1, 3):
        (pages / f"pages-{number:03d}.tex").write_text(
            plain_page(number), encoding="utf-8"
        )
    (fresh / "latex" / "main.tex").write_text(
        chr(92) + "bookinput{1}{2}\n", encoding="utf-8"
    )
    (fresh / ".reconstruct-scanned-pdf-to-latex" / "semantic-audit.json").write_text(
        json.dumps(
            {
                "owner_environments": ["bookbody", "booktext"],
                "owner_parent_environments": {"booktext": ["bookbody"]},
                "cross_page_owner_environments": [],
                "question_owner_environments": [],
                "answer_owner_environments": [],
                "answer_media_environments": [],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(fresh / "scripts" / "audit_semantics.py"),
         str(fresh)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
