"""调度器的 Git 检查点：只提交通过校验的批次。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import SCRIPTS, plain_page


def orchestrate(project, *args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "orchestrate.py"),
         str(project.root), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def git(project, *args):
    return subprocess.run(
        ["git", "-C", str(project.root), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


@pytest.fixture
def repo(batch_project):
    """A batch project inside its own scratch Git repository."""
    git(batch_project, "init")
    git(batch_project, "config", "user.email", "test@example.com")
    git(batch_project, "config", "user.name", "Test")
    git(batch_project, "add", "-A")
    git(batch_project, "commit", "-m", "baseline")
    assert orchestrate(batch_project, "plan", "--batch", "10").returncode == 0
    return batch_project


def test_checkpoint_refuses_unverified_batch(repo):
    orchestrate(repo, "next")
    # content is real, but the batch was never verified
    result = orchestrate(repo, "checkpoint", "b001-010")
    assert result.returncode == 1
    assert "尚未通过验收" in result.stderr


def test_checkpoint_refuses_stub_batch(repo):
    for number in range(1, 11):
        repo.write_page(
            number,
            "% Generated page stub; replace with reconstructed content.\n"
            f"% Source page: pages-{number:03d}\n",
        )
    # verification fails (stubs), so the batch can never reach "verified"
    assert orchestrate(repo, "verify", "b001-010").returncode == 1
    result = orchestrate(repo, "checkpoint", "b001-010")
    assert result.returncode == 1
    assert "尚未通过验收" in result.stderr


def test_checkpoint_commits_only_the_batch(repo):
    for number in range(1, 11):
        repo.write_page(number, plain_page(number))
    # an unrelated change that must NOT be swept into the batch commit
    (repo.root / "unrelated.txt").write_text("do not commit me\n", encoding="utf-8")

    assert orchestrate(repo, "verify", "b001-010").returncode == 0

    before = git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    result = orchestrate(repo, "checkpoint", "b001-010")
    assert result.returncode == 0, result.stdout + result.stderr
    after = git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    assert int(after) == int(before) + 1

    files = set(git(repo, "show", "--name-only", "--pretty=", "HEAD").stdout.split())
    assert files == {f"latex/pages/pages-{n:03d}.tex" for n in range(1, 11)}
    assert "unrelated.txt" not in files


def test_checkpoint_uses_conventional_message(repo):
    for number in range(1, 11):
        repo.write_page(number, plain_page(number))
    orchestrate(repo, "verify", "b001-010")
    orchestrate(repo, "checkpoint", "b001-010")
    message = git(repo, "log", "-1", "--pretty=%s").stdout.strip()
    assert message == "<agent><content> transcribe pages 001-010"


def test_checkpoint_accepts_explicit_message(repo):
    for number in range(1, 11):
        repo.write_page(number, plain_page(number))
    orchestrate(repo, "verify", "b001-010")
    orchestrate(repo, "checkpoint", "b001-010", "-m", "<agent><content> custom")
    assert git(repo, "log", "-1", "--pretty=%s").stdout.strip() == "<agent><content> custom"


def test_dry_run_does_not_commit(repo):
    for number in range(1, 11):
        repo.write_page(number, plain_page(number))
    orchestrate(repo, "verify", "b001-010")
    before = git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    result = orchestrate(repo, "checkpoint", "b001-010", "--dry-run")
    assert result.returncode == 0
    assert "[dry-run]" in result.stdout
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == before


def test_checkpoint_records_hash_in_state(repo):
    for number in range(1, 11):
        repo.write_page(number, plain_page(number))
    orchestrate(repo, "verify", "b001-010")
    orchestrate(repo, "checkpoint", "b001-010")
    entry = repo.dispatch_state()["batches"]["b001-010"]
    assert entry["status"] == "committed"
    head = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    assert entry["checkpoint"] == head


def test_checkpoint_outside_git_fails(batch_project):
    for number in range(1, 11):
        batch_project.write_page(number, plain_page(number))
    orchestrate(batch_project, "plan", "--batch", "10")
    # verify marks the batch verified; the Git check must then reject it
    assert orchestrate(batch_project, "verify", "b001-010").returncode == 0
    result = orchestrate(batch_project, "checkpoint", "b001-010")
    assert result.returncode == 2
    assert "不是 Git 工作树" in result.stderr


def test_checkpoint_unknown_batch_fails(repo):
    result = orchestrate(repo, "checkpoint", "b999-999")
    assert result.returncode == 2
