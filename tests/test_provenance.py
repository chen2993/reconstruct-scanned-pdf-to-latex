"""来源页标记审计。"""

from __future__ import annotations

from conftest import BS, plain_page, stub_page


def test_clean_project_passes(project, run):
    result = run("audit_provenance.py", project.root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_marker_is_reported(project, run):
    project.write_page(1, BS + "begin{bookbody}\n" + BS + "begin{booktext}\n正文。\n"
                       + BS + "end{booktext}\n" + BS + "end{bookbody}\n")
    result = run("audit_provenance.py", project.root)
    assert result.returncode == 1
    assert "missing_source_marker" in result.stdout


def test_marker_must_match_filename(project, run):
    project.write_page(1, plain_page(1).replace("pages-001", "pages-009"))
    result = run("audit_provenance.py", project.root)
    assert result.returncode == 1
    assert "source_marker_mismatch" in result.stdout


def test_duplicate_marker_in_one_file_is_reported(project, run):
    # Two markers in one file look fine visually but break traceability.
    project.write_page(1, "% Source page: pages-001\n% Source page: pages-002\n")
    result = run("audit_provenance.py", project.root)
    assert result.returncode == 1
    assert "duplicate_source_marker" in result.stdout


def test_reused_marker_across_files_is_reported(project, run):
    project.write_page(1, "% Source page: pages-001\n")
    project.write_page(2, "% Source page: pages-001\n")
    result = run("audit_provenance.py", project.root)
    assert result.returncode == 1
    assert "source_marker_reused" in result.stdout


def test_comment_form_passes(project, run):
    result = run("audit_provenance.py", project.root)
    assert result.returncode == 0


def test_empty_body_directory_fails(tmp_path, run):
    (tmp_path / "latex" / "pages").mkdir(parents=True)
    result = run("audit_provenance.py", tmp_path)
    assert result.returncode == 2


def test_stub_pages_still_carry_markers(batch_project, run):
    # The scaffolding generator writes a marker on every stub, so provenance
    # stays checkable before any content exists.
    for number in range(1, 26):
        batch_project.write_page(number, stub_page(number))
    result = run("audit_provenance.py", batch_project.root)
    assert result.returncode == 0, result.stdout
