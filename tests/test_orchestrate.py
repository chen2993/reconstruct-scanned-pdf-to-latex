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


def test_next_refuses_while_a_batch_is_unverified(planned):
    assert orchestrate(planned, "next").returncode == 0
    second = orchestrate(planned, "next")
    assert second.returncode == 1
    assert "未验收" in second.stderr


def test_next_force_overrides_the_gate(planned):
    orchestrate(planned, "next")
    forced = orchestrate(planned, "next", "--force")
    assert forced.returncode == 0

def test_concurrency_allows_that_many_batches_in_flight(batch_project):
    """并发上限是同时在跑的批次数，不是一个 boolean 派发门。"""

    orchestrate(batch_project, "plan", "--batch", "10", "--concurrency", "2")
    assert orchestrate(batch_project, "next").returncode == 0
    # 第二个批次仍可派发：1 个在飞 < 上限 2
    assert orchestrate(batch_project, "next").returncode == 0
    state = batch_project.dispatch_state()
    assert state["batches"]["b001-010"]["status"] == "dispatched"
    assert state["batches"]["b011-020"]["status"] == "dispatched"
    # 达到上限后必须排队
    blocked = orchestrate(batch_project, "next")
    assert blocked.returncode == 1
    assert "并发上限 2" in blocked.stderr


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
