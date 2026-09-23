#!/usr/bin/env python3
"""构建目标的尺寸契约：纸型尺寸的单一事实源。

为什么需要它
------------
纸型尺寸同时被两处使用：项目 ``.cls`` 里按 profile 设置 ``geometry``，构建后的
成品审计又要按 profile 核对 MediaBox。两边各写一套数字，早晚会漂移——而漂移的
表现是"审计说尺寸对、成品其实不对"或反过来的假失败。本文件是唯一来源。

项目自己的尺寸（``original``）由项目确认后写入 ``profile-overrides.json``；
本文件只固定与书无关的通用做题本纸型，不把某一本书的尺寸写死。
"""

from __future__ import annotations

import json
from pathlib import Path

# 点与毫米的换算（PDF 用户单位是 1/72 英寸）。
POINTS_PER_MM = 72.0 / 25.4

# 与原书无关的通用做题本纸型，单位毫米、竖版为 (宽, 高)。
# 横向 Pad 按"宽 > 高"记录，与 PDF MediaBox 一致。
BUILTIN_PROFILE_MM: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "pad13": (280.0, 210.0),
    "pad11": (280.0, 193.0),
}

# MediaBox 允许的偏差：印刷与 PDF 取整会带来零点几毫米的差异。
SIZE_TOLERANCE_MM = 0.8

OVERRIDES_FILENAME = "profile-overrides.json"


class ProfileError(RuntimeError):
    """尺寸契约不完整或不可用；调用方应停下来请人工确认，而不是猜。"""


def load_overrides(project: Path | None) -> dict[str, tuple[float, float]]:
    """读取项目确认过的纸型尺寸（含 ``original``）。

    项目必须显式登记原书尺寸，因为只有原件能决定它；缺登记时 ``original``
    在 :func:`expected_mm` 里会报错，而不是退回某个"常见开本"。
    """
    if project is None:
        return {}
    path = Path(project) / ".reconstruct-scanned-pdf-to-latex" / OVERRIDES_FILENAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"无法读取纸型登记 {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProfileError(f"纸型登记顶层必须是对象: {path}")
    result: dict[str, tuple[float, float]] = {}
    for name, value in payload.items():
        # `_` 开头的是给人看的说明键（_comment/_format/...），不是纸型登记。
        if str(name).startswith("_"):
            continue
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ProfileError(f"纸型 {name!r} 必须是 [宽mm, 高mm]")
        try:
            width, height = (float(item) for item in value)
        except (TypeError, ValueError) as exc:
            raise ProfileError(f"纸型 {name!r} 的尺寸不是数字") from exc
        if width <= 0 or height <= 0:
            raise ProfileError(f"纸型 {name!r} 的尺寸必须为正")
        result[str(name)] = (width, height)
    return result


def expected_mm(profile: str, project: Path | None = None) -> tuple[float, float]:
    """返回某 profile 期望的 (宽mm, 高mm)。"""
    overrides = load_overrides(project)
    if profile in overrides:
        return overrides[profile]
    if profile in BUILTIN_PROFILE_MM:
        return BUILTIN_PROFILE_MM[profile]
    raise ProfileError(
        f"未知或未登记的纸型 {profile!r}。a4/pad11/pad13 是内置的目标尺寸；"
        "original（或项目自订纸型）必须先在 "
        f".reconstruct-scanned-pdf-to-latex/{OVERRIDES_FILENAME} 里登记经确认的尺寸。"
    )


def within_tolerance(
    actual_mm: tuple[float, float], expected: tuple[float, float]
) -> bool:
    return all(
        abs(value - target) <= SIZE_TOLERANCE_MM
        for value, target in zip(actual_mm, expected)
    )


def describe(project: Path | None = None) -> str:
    """人读的尺寸契约摘要，用于审计输出的报告行。"""
    lines = ["内置纸型(mm)："]
    for name, (width, height) in sorted(BUILTIN_PROFILE_MM.items()):
        lines.append(f"  {name:8s} {width:.1f} × {height:.1f}")
    overrides = load_overrides(project)
    if overrides:
        lines.append("项目登记(mm)：")
        for name, (width, height) in sorted(overrides.items()):
            lines.append(f"  {name:8s} {width:.1f} × {height:.1f}")
    else:
        lines.append("项目登记：无（original 未登记时会报错，不会退回常见开本）")
    return "\n".join(lines)
