"""Smoke tests — prove the skeleton loads and the CLI wires up.

These are intentionally shallow. Real detector tests arrive with the
detectors themselves in the next milestone.
"""

from __future__ import annotations

from click.testing import CliRunner

from archdogma import __version__
from archdogma.cli import main


def test_version_is_set() -> None:
    assert __version__
    assert isinstance(__version__, str)


def test_version_matches_pyproject() -> None:
    """Drift between the two version strings shipped a wrong --version once."""
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not pyproject.exists():  # installed without the source tree
        return
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert declared == __version__


def test_cli_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help_mentions_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "probe" in result.output
    assert "dogmas" in result.output
