"""调度器：切批、任务包、验收与 Git 检查点。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import BS, SCRIPTS, plain_page, stub_page


def orchestrate(project, *args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "orchestrate.py"),
         str(project.root), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


@pytest.fixture
def planned(batch_project):
    # batch_project pages are real content, not stubs
    result = orchestrate(batch_project, "plan", "--batch", "10")
    assert result.returncode == 0, result.stderr
    return batch_project


def test_plan_uses_declared_body_range(planned):
    state = planned.dispatch_state()
    assert list(state["batches"]) == ["b001-010", "b011-020", "b021-025"]


def test_plan_reflects_partial_last_batch(planned):
    state = planned.dispatch_state()
    assert state["batches"]["b021-025"]["end"] == 25


def test_status_lists_every_batch(planned):
    result = orchestrate(planned, "status")
    assert result.returncode == 0
    for identifier in ("b001-010", "b011-020", "b021-025"):
        assert identifier in result.stdout


def test_next_creates_task_packet(planned):
    result = orchestrate(planned, "next")
    assert result.returncode == 0, result.stderr
    packet = planned.control / "dispatch" / "b001-010.md"
    assert packet.is_file()
    text = packet.read_text(encoding="utf-8")
    assert "样式摘要版本: v1" in text
    assert "latex/pages/pages-001.tex" in text
    assert "停工反馈" in text


def test_next_does_not_gate_by_default(planned):
    """默认不设人为上限：连续 next 不应被排队门拦住。

    真实并发上限由运行环境决定，脚本猜不出这个数字，写死只会白等。
    """

    for _ in range(3):
        result = orchestrate(planned, "next")
        assert result.returncode == 0, result.stderr
    state = planned.dispatch_state()
    assert state["batches"]["b001-010"]["status"] == "dispatched"
    assert state["batches"]["b011-020"]["status"] == "dispatched"
    assert state["batches"]["b021-025"]["status"] == "dispatched"

def test_default_concurrency_is_unbounded(planned):
    assert planned.dispatch_state()["concurrency"] == 0

def test_next_count_dispatches_several_at_once(batch_project):
    """一次调用填满流水线，而不是连调多次。"""

    orchestrate(batch_project, "plan", "--batch", "10")
    result = orchestrate(batch_project, "next", "--count", "2")
    assert result.returncode == 0, result.stderr
    state = batch_project.dispatch_state()
    assert state["batches"]["b001-010"]["status"] == "dispatched"
    assert state["batches"]["b011-020"]["status"] == "dispatched"
    assert state["batches"]["b021-025"]["status"] == "pending"

def test_next_count_zero_dispatches_everything_pending(batch_project):
    orchestrate(batch_project, "plan", "--batch", "10")
    result = orchestrate(batch_project, "next", "--count", "0")
    assert result.returncode == 0, result.stderr
    state = batch_project.dispatch_state()
    assert all(entry["status"] == "dispatched" for entry in state["batches"].values())

def test_soft_limit_still_available_when_configured(batch_project):
    """显式设了软上限才启用排队门。"""

    assert orchestrate(batch_project, "plan", "--batch", "10", "--concurrency", "2").returncode == 0
    assert orchestrate(batch_project, "next").returncode == 0
    assert orchestrate(batch_project, "next").returncode == 0
    blocked = orchestrate(batch_project, "next")
    assert blocked.returncode == 1
    assert "软上限 2" in blocked.stderr

def test_soft_limit_can_be_overridden_with_force(batch_project):
    orchestrate(batch_project, "plan", "--batch", "10", "--concurrency", "1")
    assert orchestrate(batch_project, "next").returncode == 0
    overridden = orchestrate(batch_project, "next", "--force")
    assert overridden.returncode == 0, overridden.stderr

def test_negative_concurrency_is_rejected(batch_project):
    result = orchestrate(batch_project, "plan", "--concurrency", "-1")
    assert result.returncode == 2
    assert "不能为负数" in result.stderr

def test_negative_count_is_rejected(batch_project):
    orchestrate(batch_project, "plan", "--batch", "10")
    result = orchestrate(batch_project, "next", "--count", "-1")
    assert result.returncode == 2
    assert "不能为负数" in result.stderr

def test_packet_reports_cross_page_handoff(batch_project):
    # an example spans pages 6..7, i.e. inside the first batch
    batch_project.write_page(
        6,
        "% Source page: pages-006\n"
        + BS + "begin{bookbody}\n"
        + BS + "begin{booktext}\n正文。\n" + BS + "end{booktext}\n"
        + BS + "begin{bookexample}\n题干开头。\n",
    )
    batch_project.write_page(
        7,
        "% Source page: pages-007\n"
        + BS + "begin{bookanswer}\n解答。\n" + BS + "end{bookanswer}\n"
        + BS + "end{bookexample}\n"
        + BS + "begin{booktext}\n本页正文。\n" + BS + "end{booktext}\n"
        + BS + "end{bookbody}\n",
    )
    orchestrate(batch_project, "plan", "--batch", "10")
    orchestrate(batch_project, "next")
    text = (batch_project.control / "dispatch" / "b001-010.md").read_text(encoding="utf-8")
    assert "跨页交接" in text
    assert "`bookexample`" in text
    assert "不得另开新环境边界" in text


def test_packet_warns_about_unregistered_open_owner(batch_project):
    batch_project.write_page(
        6,
        "% Source page: pages-006\n"
        + BS + "begin{bookbody}\n"
        + BS + "begin{bookexample}\n题干开头。\n",
    )
    # leave page 7 and the example unclosed; remove the cross-page registration
    batch_project.write_config(
        {
            "owner_environments": ["bookbody", "booktext", "bookexample"],
            "owner_parent_environments": {
                "booktext": ["bookbody"],
                "bookexample": ["bookbody"],
            },
            "cross_page_owner_environments": [],
            "question_owner_environments": ["bookexample"],
            "answer_owner_environments": [],
            "answer_media_environments": [],
        }
    )
    orchestrate(batch_project, "plan", "--batch", "10")
    orchestrate(batch_project, "next")
    text = (batch_project.control / "dispatch" / "b001-010.md").read_text(encoding="utf-8")
    assert "未登记为可跨页所有者" in text


def test_verify_rejects_stub_batch(planned):
    for number in range(1, 11):
        planned.write_page(number, stub_page(number))
    result = orchestrate(planned, "verify", "b001-010")
    assert result.returncode == 1
    assert "仍是占位骨架" in result.stdout


def test_verify_accepts_transcribed_batch(planned):
    for number in range(1, 11):
        planned.write_page(number, plain_page(number))
    result = orchestrate(planned, "verify", "b001-010")
    assert result.returncode == 0, result.stdout
    assert planned.dispatch_state()["batches"]["b001-010"]["status"] == "verified"


def test_verify_marks_failed_batch_in_progress(planned):
    for number in range(1, 11):
        planned.write_page(number, stub_page(number))
    result = orchestrate(planned, "verify", "b001-010")
    assert result.returncode == 1
    assert planned.dispatch_state()["batches"]["b001-010"]["status"] == "in_progress"


def test_verify_unknown_batch_fails(planned):
    result = orchestrate(planned, "verify", "b999-999")
    assert result.returncode == 2


def test_next_without_plan_fails(batch_project):
    result = orchestrate(batch_project, "next")
    assert result.returncode == 2
    assert "尚未规划" in result.stderr


def test_plan_rejects_non_positive_batch_size(batch_project):
    result = orchestrate(batch_project, "plan", "--batch", "0")
    assert result.returncode == 2


def test_config_error_is_reported_without_traceback(batch_project):
    batch_project.write_config({"owner_environments": "bad"})
    result = orchestrate(batch_project, "plan")
    assert result.returncode == 2
    assert "语义审计配置错误" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_main_fails(tmp_path, batch_project):
    (batch_project.root / "latex" / "main.tex").unlink()
    result = orchestrate(batch_project, "plan")
    assert result.returncode == 2
    assert "唯一入口" in result.stderr
