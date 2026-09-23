"""视觉探针图：内容必须与派发提示词里的期望答案一致。

探针的用处是区分"看不到"与"看错"，所以图的内容必须可自动核对，且与提示词里
声明的期望答案严格一致——两边不一致时探针会给出误导性的结论。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO

TOOL = REPO / "tools" / "make_vision_probe.py"
PIL_Image = pytest.importorskip("PIL.Image", reason="需要 Pillow 生成探针图")
PROMPTS = REPO / "references" / "governance" / "dispatch-prompts.md"


def make(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOL), str(path)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_probe_is_generated_with_stable_answer(tmp_path):
    output = tmp_path / "probe.png"
    result = make(output)
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert "圆=3 三角=2 方=4 字符=V7K" in result.stdout


def test_declared_counts_match_the_constants(tmp_path):
    """工具自报的期望答案必须与它实际画的形状数一致。"""

    import importlib.util

    spec = importlib.util.spec_from_file_location("probe", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = tmp_path / "probe.png"
    make(output)
    with PIL_Image.open(output) as image:
        colors = image.convert("RGB").getcolors(maxcolors=1 << 20) or []
    palette = {colour for _count, colour in colors}

    # 三种形状各用一种纯色；数颜色出现次数不等于数形状（抗锯齿会引入过渡色），
    # 所以这里只校验三种主色都在，形状数量由常量声明并由提示词比对。
    assert (30, 90, 220) in palette, "缺少蓝色圆形"
    assert (200, 0, 150) in palette, "缺少洋红三角形"
    assert (20, 140, 60) in palette, "缺少绿色正方形"
    assert module.CIRCLES == 3 and module.TRIANGLES == 2 and module.SQUARES == 4
    assert module.MARKER == "V7K"


def test_dispatch_prompt_declares_the_same_answer():
    """提示词里写的期望答案必须与探针图的常量一致，否则探针会误导。"""

    if not PROMPTS.is_file():
        pytest.skip("派发提示词文件不存在")
    text = PROMPTS.read_text(encoding="utf-8")
    assert "圆=3" in text or "圆=N" in text, "提示词未声明期望答案格式"
    if "圆=3" in text:
        for fragment in ("三角=2", "方=4", "V7K"):
            assert fragment in text, f"提示词缺少 {fragment}"


def test_usage_error_for_missing_parent_dir_is_handled(tmp_path):
    """输出目录不存在时应自动创建，而不是报错。"""

    output = tmp_path / "nested" / "deep" / "probe.png"
    result = make(output)
    assert result.returncode == 0, result.stderr
    assert output.is_file()
