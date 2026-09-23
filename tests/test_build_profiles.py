"""纸型契约：尺寸的单一事实源。

尺寸同时被 .cls 与成品审计使用；两边各写一套会漂移，而漂移的表现是
"审计说对、成品其实不对"或反过来的假失败。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from build_profiles import (  # noqa: E402
    POINTS_PER_MM,
    ProfileError,
    expected_mm,
    load_overrides,
    within_tolerance,
)

fitz = pytest.importorskip("fitz", reason="需要 PyMuPDF 生成测试 PDF")
PIL_Image = pytest.importorskip("PIL.Image", reason="需要 Pillow 生成测试图像")

AUDITOR = SCRIPTS / "audit_pdf_build.py"


def test_builtin_profiles_are_available():
    assert expected_mm("a4") == (210.0, 297.0)
    assert expected_mm("pad11") == (280.0, 193.0)
    assert expected_mm("pad13") == (280.0, 210.0)


def test_unregistered_original_is_an_error(tmp_path):
    """原件尺寸只有原件能决定：未登记时必须报错，而不是退回常见开本。"""

    with pytest.raises(ProfileError, match="未登记"):
        expected_mm("original", tmp_path)


def test_project_overrides_are_read(tmp_path):
    control = tmp_path / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True)
    (control / "profile-overrides.json").write_text(
        json.dumps({"original": [185.0, 260.0]}), encoding="utf-8"
    )
    assert load_overrides(tmp_path) == {"original": (185.0, 260.0)}
    assert expected_mm("original", tmp_path) == (185.0, 260.0)


@pytest.mark.parametrize(
    "payload",
    [
        {"original": [185.0]},
        {"original": [185.0, 260.0, 1.0]},
        {"original": ["a", "b"]},
        {"original": [-1.0, 260.0]},
    ],
)
def test_bad_overrides_are_rejected(tmp_path, payload):
    control = tmp_path / ".reconstruct-scanned-pdf-to-latex"
    control.mkdir(parents=True)
    (control / "profile-overrides.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProfileError):
        load_overrides(tmp_path)


def test_tolerance_handles_pdf_rounding():
    assert within_tolerance((210.0, 297.0), (210.0, 297.0))
    assert within_tolerance((209.5, 297.4), (210.0, 297.0))
    assert not within_tolerance((196.0, 272.0), (210.0, 297.0))


def make_pdf(path: Path, width_mm: float, height_mm: float, pages: int = 2) -> Path:
    document = fitz.open()
    for _ in range(pages):
        page = document.new_page(
            width=width_mm * POINTS_PER_MM, height=height_mm * POINTS_PER_MM
        )
        page.insert_text((30, 60), "content")
    document.save(path)
    document.close()
    return path


def audit(pdf: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(AUDITOR), str(pdf), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_profile_match_passes(tmp_path):
    pdf = make_pdf(tmp_path / "a4.pdf", 210.0, 297.0)
    result = audit(pdf, "--profile", "a4")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "核对 a4" in result.stdout


def test_profile_mismatch_fails_per_page(tmp_path):
    """逐页核对：只看"集合里有正确的尺寸"会漏掉真正混错的那几页。"""

    pdf = make_pdf(tmp_path / "wrong.pdf", 196.0, 272.0)
    result = audit(pdf, "--profile", "a4")
    assert result.returncode == 1
    assert "纸型不符" in result.stderr


def test_mixed_sizes_are_caught(tmp_path):
    """同一目标里混进一页别的纸型，必须报出来。"""

    document = fitz.open()
    good = document.new_page(width=210 * POINTS_PER_MM, height=297 * POINTS_PER_MM)
    good.insert_text((30, 60), "ok")
    bad = document.new_page(width=196 * POINTS_PER_MM, height=272 * POINTS_PER_MM)
    bad.insert_text((30, 60), "wrong size")
    pdf = tmp_path / "mixed.pdf"
    document.save(pdf)
    document.close()

    result = audit(pdf, "--profile", "a4")
    assert result.returncode == 1
    assert "第 2 页纸型不符" in result.stderr


def test_unregistered_profile_is_a_usage_error(tmp_path):
    pdf = make_pdf(tmp_path / "a4.pdf", 210.0, 297.0)
    result = audit(pdf, "--profile", "original")
    assert result.returncode == 2
    assert "未登记" in result.stderr


def test_without_profile_no_size_check(tmp_path):
    """省略 --profile 时只报告实际纸型，不判定对错。"""

    pdf = make_pdf(tmp_path / "any.pdf", 196.0, 272.0)
    result = audit(pdf)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "纸型集合" in result.stdout
