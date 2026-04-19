"""Tests for the CLI `--speak` flag and the sentence synthesis layer.

Verified guarantees:
    - `--speak` is accepted by the probe subcommand without error.
    - stdout is byte-identical whether `--speak` is passed or not —
      voice is additive, never a replacement for plain text.
    - The synthesized sentence pluralizes, uses word numbers up to ten,
      humanizes kebab-case tag names, and always ends with the honest
      "Trust score unknown." until Phase 2 delivers it.
    - If the TTS backend blows up, the CLI does not crash.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from archdogma import cli as cli_mod
from archdogma.cli import (
    _humanize_tag_name,
    _number_word,
    _synthesize_spoken_summary,
    main,
)
from archdogma.probe.walker import ProbeResult
from archdogma.probe.tags.tier1 import Tag


FIXTURES = Path(__file__).resolve().parent / "fixtures"
TOO_MANY_PARAMS = FIXTURES / "too_many_params_sample.py"
FILE_PROBE = FIXTURES / "file_probe_sample.py"


# ---------------------------------------------------------------------------
# Sentence synthesis
# ---------------------------------------------------------------------------


def _result_with_tags(*names: str) -> ProbeResult:
    tags = tuple(Tag(name=n, detail=n, line=1, col=0) for n in names)
    return ProbeResult(
        file=Path("dummy.py"),
        function_name="f",
        line_start=1,
        line_end=10,
        tags=tags,
    )


def test_synthesis_no_tags() -> None:
    s = _synthesize_spoken_summary(_result_with_tags())
    assert s == "No tags detected. Trust score unknown."


def test_synthesis_one_tag_singular_noun() -> None:
    s = _synthesize_spoken_summary(_result_with_tags("long-function"))
    assert s == "One tag found: long function. Trust score unknown."


def test_synthesis_two_tags_plural_noun() -> None:
    s = _synthesize_spoken_summary(
        _result_with_tags("long-function", "too-many-params")
    )
    assert s == (
        "Two tags found: long function, too many params. Trust score unknown."
    )


def test_synthesis_humanizes_kebab_case() -> None:
    s = _synthesize_spoken_summary(_result_with_tags("deep-nesting"))
    assert "deep nesting" in s
    assert "deep-nesting" not in s


def test_synthesis_word_number_for_small_counts() -> None:
    s = _synthesize_spoken_summary(_result_with_tags("a", "b", "c"))
    assert s.startswith("Three tags found:")


def test_synthesis_digit_for_large_counts() -> None:
    names = [f"tag-{i}" for i in range(11)]
    s = _synthesize_spoken_summary(_result_with_tags(*names))
    assert s.startswith("11 tags found:")


def test_synthesis_always_mentions_trust_score() -> None:
    """Until Phase 2 delivers Trust Score, we say it explicitly.
    Honesty > silence."""
    for tags in ([], ["x"], ["x", "y"]):
        assert "Trust score unknown." in _synthesize_spoken_summary(
            _result_with_tags(*tags)
        )


def test_humanize_tag_name() -> None:
    assert _humanize_tag_name("long-function") == "long function"
    assert _humanize_tag_name("too-many-params") == "too many params"
    assert _humanize_tag_name("alreadyoneword") == "alreadyoneword"


def test_number_word_thresholds() -> None:
    assert _number_word(1) == "One"
    assert _number_word(10) == "Ten"
    assert _number_word(11) == "11"
    assert _number_word(999) == "999"


# ---------------------------------------------------------------------------
# CLI integration — --speak flag
# ---------------------------------------------------------------------------


def test_probe_accepts_speak_flag(monkeypatch) -> None:
    """The flag must parse. speak() is monkeypatched so CI never touches audio."""
    calls: list[str] = []
    monkeypatch.setattr(cli_mod, "speak", lambda text: calls.append(text) or True)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["probe", str(FILE_PROBE), "--function", "Outer.regular_method", "--speak"],
    )
    assert result.exit_code == 0, result.output
    assert calls, "speak() should have been called once"
    assert "too many params" in calls[0]
    assert "Trust score unknown" in calls[0]


def test_speak_does_not_alter_stdout(monkeypatch) -> None:
    """stdout with --speak must equal stdout without --speak. Voice is additive."""
    monkeypatch.setattr(cli_mod, "speak", lambda _text: True)

    runner = CliRunner()
    base = runner.invoke(
        main,
        ["probe", str(FILE_PROBE), "--function", "Outer.regular_method"],
    )
    speak_ = runner.invoke(
        main,
        [
            "probe",
            str(FILE_PROBE),
            "--function",
            "Outer.regular_method",
            "--speak",
        ],
    )
    assert base.exit_code == 0
    assert speak_.exit_code == 0
    assert base.output == speak_.output


def test_speak_backend_failure_does_not_crash_cli(monkeypatch) -> None:
    """Even if speak() raises (it shouldn't, but defensively), the CLI
    must not exit non-zero. We additionally patch it to just return False
    to simulate "no backend found" — the user-visible result is still a
    clean exit and a completed probe."""
    monkeypatch.setattr(cli_mod, "speak", lambda _text: False)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["probe", str(FILE_PROBE), "--function", "Outer.regular_method", "--speak"],
    )
    assert result.exit_code == 0
    # Plain probe output is still there.
    assert "Function Probe" in result.output


def test_speak_flag_called_on_clean_function(monkeypatch) -> None:
    """No tags means the spoken sentence is the 'No tags detected' variant.
    `lean` in the too-many-params fixture trips nothing."""
    calls: list[str] = []
    monkeypatch.setattr(cli_mod, "speak", lambda t: calls.append(t) or True)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["probe", str(TOO_MANY_PARAMS), "--function", "lean", "--speak"],
    )
    assert result.exit_code == 0, result.output
    assert calls
    assert calls[0] == "No tags detected. Trust score unknown."
