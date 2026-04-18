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
