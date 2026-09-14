"""语义审计：所有权、跨页环境与集中职责。"""

from __future__ import annotations

import json

from conftest import BS, MINIMAL_CONFIG, stub_page


def test_clean_project_passes(project, run):
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_json_report_shape(project, run):
    result = run("audit_semantics.py", project.root, "--json")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    # front/cover.tex + the two body pages
    assert payload["files_audited"] == 3
    assert payload["issues"] == []


def test_cross_page_owner_is_allowed(project, run):
    # The example (and its enclosing body owner) flow across the boundary, so
    # both must be registered as cross-page.
    config = dict(MINIMAL_CONFIG)
    config["cross_page_owner_environments"] = [
        "bookbody",
        "bookexample",
        "bookanswer",
    ]
    project.write_config(config)
    project.write_page(
        1,
        "% Source page: pages-001\n"
        + BS + "begin{bookbody}\n"
        + BS + "begin{booktext}\n开头。\n" + BS + "end{booktext}\n"
        + BS + "begin{bookexample}\n题干开头。\n",
    )
    project.write_page(
        2,
        "% Source page: pages-002\n"
        + BS + "begin{bookanswer}\n解答。\n" + BS + "end{bookanswer}\n"
        + BS + "end{bookexample}\n"
        + BS + "begin{booktext}\n本页正文。\n" + BS + "end{booktext}\n"
        + BS + "end{bookbody}\n",
    )
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 0, result.stdout


def test_unregistered_cross_page_owner_is_rejected(project, run):
    config = dict(MINIMAL_CONFIG)
    config["cross_page_owner_environments"] = []
    project.write_config(config)
    project.write_page(
        1,
        "% Source page: pages-001\n"
        + BS + "begin{bookbody}\n"
        + BS + "begin{booktext}\n开头。\n" + BS + "end{booktext}\n"
        + BS + "begin{bookexample}\n题干开头。\n",
    )
    project.write_page(
        2,
        "% Source page: pages-002\n"
        + BS + "begin{bookanswer}\n解答。\n" + BS + "end{bookanswer}\n"
        + BS + "end{bookexample}\n"
        + BS + "begin{booktext}\n本页正文。\n" + BS + "end{booktext}\n"
        + BS + "end{bookbody}\n",
    )
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 1
    assert "cross_page_environment_not_allowed" in result.stdout


def test_hardcoded_command_is_rejected(project, run):
    project.write_page(
        1,
        "% Source page: pages-001\n"
        + BS + "setcounter{bookexample}{7}\n"
        + BS + "begin{bookbody}\n" + BS + "begin{booktext}\n正文。\n"
        + BS + "end{booktext}\n" + BS + "end{bookbody}\n",
    )
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 1
    # assert on the exact issue code, not a substring that a rename would keep
    assert "hardcoded_command:" in result.stdout


def test_bare_text_without_owner_is_rejected(project, run):
    project.write_page(1, "% Source page: pages-001\n无所有者的裸文本。\n")
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 1
    assert "bare_text" in result.stdout


def test_owner_parent_whitelist_is_enforced(project, run):
    # bookanswer must live inside bookexample, so a root-level one is invalid
    project.write_page(
        1,
        "% Source page: pages-001\n"
        + BS + "begin{bookbody}\n"
        + BS + "begin{bookanswer}\n答案。\n"
        + BS + "end{bookanswer}\n"
        + BS + "end{bookbody}\n",
    )
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 1
    assert "owner_parent_not_allowed" in result.stdout


def test_invalid_config_is_reported_cleanly(project, run):
    project.write_config({"owner_environments": "not-a-list"})
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 2
    assert "语义审计配置错误" in result.stderr
    assert "Traceback" not in result.stderr


def test_config_referencing_unregistered_parent_fails(project, run):
    project.write_config(
        {
            "owner_environments": ["bookbody"],
            "owner_parent_environments": {"booktext": ["bookbody"]},
        }
    )
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 2
    assert "语义审计配置错误" in result.stderr


def test_missing_entry_file_fails(tmp_path, run):
    result = run("audit_semantics.py", tmp_path)
    assert result.returncode == 2
    assert "缺少唯一入口" in result.stderr


def test_comment_only_stub_is_not_a_semantic_error(project, run):
    # A stub contains only comments, so there is no bare content to report;
    # detecting unfinished stubs is the dispatcher's job, not this auditor's.
    project.write_page(1, stub_page(1))
    result = run("audit_semantics.py", project.root)
    assert result.returncode == 0


def test_json_error_output_is_machine_readable(tmp_path, run):
    result = run("audit_semantics.py", tmp_path, "--json")
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_error"
