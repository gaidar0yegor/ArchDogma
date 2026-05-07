"""Tests for the scan command and scanner module."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from archdogma.cli import main
from archdogma.probe.scanner import FileScanResult, collect_python_files, scan_file


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_py(tmp_path: Path):
    """Factory: write Python source to a temp file and return its path."""

    def _write(name: str, src: str) -> Path:
        p = tmp_path / name
        p.write_text(textwrap.dedent(src), encoding="utf-8")
        return p

    return _write


@pytest.fixture()
def clean_file(tmp_py):
    return tmp_py(
        "clean.py",
        """\
        def add(a: int, b: int) -> int:
            return a + b
        """,
    )


@pytest.fixture()
def flagged_file(tmp_py):
    """A file with a long function (>80 LOC)."""
    body = "    x = 0\n" * 82
    return tmp_py("flagged.py", f"def long_fn():\n{body}")


@pytest.fixture()
def syntax_error_file(tmp_py):
    return tmp_py("broken.py", "def f(\n  # unclosed\n")


# ---------------------------------------------------------------------------
# scan_file
# ---------------------------------------------------------------------------


def test_scan_file_clean(clean_file: Path) -> None:
    result = scan_file(clean_file)
    assert result.parse_error is None
    assert not result.has_tags
    assert result.tag_count == 0


def test_scan_file_flagged(flagged_file: Path) -> None:
    result = scan_file(flagged_file)
    assert result.parse_error is None
    assert result.has_tags
    assert result.tag_count >= 1
    tag_names = {t.name for r in result.results for t in r.tags}
    assert "long-function" in tag_names


def test_scan_file_parse_error(syntax_error_file: Path) -> None:
    result = scan_file(syntax_error_file)
    assert result.parse_error is not None
    assert result.results == ()
    assert result.tag_count == 0


def test_scan_file_with_god_class(tmp_py) -> None:
    methods = "\n".join(f"    def method_{i}(self): pass" for i in range(20))
    src = f"class Big:\n{methods}\n"
    p = tmp_py("godclass.py", src)
    result = scan_file(p)
    assert result.parse_error is None
    tag_names = {t.name for r in result.results for t in r.tags}
    assert "god-class" in tag_names


def test_scan_file_both_functions_and_classes(tmp_py) -> None:
    body = "    x = 0\n" * 82
    methods = "\n".join(f"    def method_{i}(self): pass" for i in range(20))
    src = f"def long_fn():\n{body}\n\nclass Big:\n{methods}\n"
    p = tmp_py("mixed.py", src)
    result = scan_file(p)
    assert result.parse_error is None
    # Should have results for both the function and the class
    names = {r.function_name for r in result.results}
    assert "long_fn" in names
    assert "Big" in names


# ---------------------------------------------------------------------------
# collect_python_files
# ---------------------------------------------------------------------------


def test_collect_single_file(clean_file: Path) -> None:
    files = list(collect_python_files(clean_file))
    assert files == [clean_file]


def test_collect_skips_pycache(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1")
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "sneaky.py").write_text("z = 3")
    files = list(collect_python_files(tmp_path))
    assert {f.name for f in files} == {"a.py"}


def test_collect_skips_venv(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("pass")
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "lib.py").write_text("pass")
    files = list(collect_python_files(tmp_path))
    assert {f.name for f in files} == {"app.py"}


def test_collect_excludes_pattern(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("pass")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("pass")
    files = list(collect_python_files(tmp_path, excludes=("tests/**",)))
    assert {f.name for f in files} == {"main.py"}


def test_collect_directory_sorted(tmp_path: Path) -> None:
    for name in ("c.py", "a.py", "b.py"):
        (tmp_path / name).write_text("pass")
    files = list(collect_python_files(tmp_path))
    assert [f.name for f in files] == ["a.py", "b.py", "c.py"]


# ---------------------------------------------------------------------------
# CLI scan command
# ---------------------------------------------------------------------------


def test_cli_scan_no_tags_exits_zero(clean_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(clean_file)])
    assert result.exit_code == 0, result.output


def test_cli_scan_with_tags_exits_nonzero(flagged_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(flagged_file)])
    assert result.exit_code == 1


def test_cli_scan_no_fail_exits_zero(flagged_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--no-fail", str(flagged_file)])
    assert result.exit_code == 0, result.output


def test_cli_scan_summary_hides_details(flagged_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["scan", "--no-fail", "--summary", str(flagged_file)]
    )
    assert "Scanned" in result.output
    assert "[long-function]" not in result.output


def test_cli_scan_plain_shows_details(flagged_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--no-fail", str(flagged_file)])
    assert "[long-function]" in result.output
    assert "Scanned" in result.output


def test_cli_scan_json_format(flagged_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["scan", "--no-fail", "--format", "json", str(flagged_file)]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tags"] >= 1
    assert len(data["files"]) >= 1
    assert data["files"][0]["items"][0]["tags"][0]["name"] == "long-function"


def test_cli_scan_json_clean_file_has_no_flagged_files(clean_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["scan", "--format", "json", str(clean_file)]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tags"] == 0
    assert data["files"] == []


def test_cli_scan_empty_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "No Python files found" in result.output


def test_cli_scan_directory_summary(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("def f(): return 1\n")
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "Scanned" in result.output
