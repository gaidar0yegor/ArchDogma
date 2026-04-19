"""Tests for the voice.speak module.

The contract is narrow and must hold:
    1. speak() never raises — audio failures are always soft.
    2. Empty / whitespace input is a silent no-op.
    3. Backend selection picks native tools first.
    4. Subprocess failures and pyttsx3 import/runtime errors are swallowed
       and a single dedup'd stderr warning is printed.

We mock everything at the subprocess boundary so the real `say` / `espeak-ng`
are never invoked during CI. That way the suite is deterministic on any box.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from archdogma.voice import speak as speak_mod
from archdogma.voice.speak import speak


@pytest.fixture(autouse=True)
def _reset_warnings():
    """Each test starts with a clean dedup set — otherwise warning assertions
    become order-dependent across the suite."""
    speak_mod._reset_warnings()
    yield
    speak_mod._reset_warnings()


# ---------------------------------------------------------------------------
# Empty / whitespace input is a silent no-op
# ---------------------------------------------------------------------------


def test_speak_empty_string_returns_false() -> None:
    assert speak("") is False


def test_speak_whitespace_only_returns_false() -> None:
    assert speak("   \n\t  ") is False


def test_speak_empty_does_not_call_backend(monkeypatch) -> None:
    """Empty input must short-circuit before any subprocess call."""
    called: list[str] = []

    def fake_run(*a, **kw):  # pragma: no cover — must not be called
        called.append("subprocess")
        raise AssertionError("backend must not be invoked for empty text")

    monkeypatch.setattr(subprocess, "run", fake_run)
    speak("")
    speak("   ")
    assert called == []


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def test_macos_prefers_say(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        speak_mod.shutil,
        "which",
        lambda name: "/usr/bin/say" if name == "say" else None,
    )
    backend = speak_mod._choose_backend()
    assert backend is speak_mod._say_backend


def test_linux_prefers_espeak(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        speak_mod.shutil,
        "which",
        lambda name: "/usr/bin/espeak-ng" if name == "espeak-ng" else None,
    )
    # pyttsx3 shouldn't even matter — native wins on Linux when present.
    monkeypatch.setattr(speak_mod, "_pyttsx3_available", lambda: True)
    backend = speak_mod._choose_backend()
    assert backend is speak_mod._espeak_backend


def test_windows_falls_back_to_pyttsx3(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(speak_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(speak_mod, "_pyttsx3_available", lambda: True)
    backend = speak_mod._choose_backend()
    assert backend is speak_mod._pyttsx3_backend


def test_no_backend_available_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "freebsd")
    monkeypatch.setattr(speak_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(speak_mod, "_pyttsx3_available", lambda: False)
    assert speak_mod._choose_backend() is None


def test_linux_without_espeak_falls_back_to_pyttsx3(monkeypatch) -> None:
    """If espeak-ng isn't on PATH on Linux, pyttsx3 is the next try —
    not a hard fail. Users should still get *some* voice."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(speak_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(speak_mod, "_pyttsx3_available", lambda: True)
    assert speak_mod._choose_backend() is speak_mod._pyttsx3_backend


def test_macos_without_say_falls_back_to_pyttsx3(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(speak_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(speak_mod, "_pyttsx3_available", lambda: True)
    assert speak_mod._choose_backend() is speak_mod._pyttsx3_backend


# ---------------------------------------------------------------------------
# speak() top-level: never-crash contract
# ---------------------------------------------------------------------------


def test_speak_returns_false_and_warns_when_no_backend(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(speak_mod, "_choose_backend", lambda: None)
    assert speak("hello") is False
    err = capsys.readouterr().err
    assert "no TTS backend" in err


def test_speak_survives_missing_binary(monkeypatch, capsys) -> None:
    """shutil.which reports the binary exists, but subprocess.run raises
    FileNotFoundError anyway (race / broken PATH entry / sandbox). Must not
    crash the CLI — that would violate the accessibility contract."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(speak_mod.shutil, "which", lambda _n: "/usr/bin/say")

    def raise_fnf(*a, **kw):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(subprocess, "run", raise_fnf)
    assert speak("hello") is False
    err = capsys.readouterr().err
    assert "`say` failed" in err


def test_speak_survives_subprocess_timeout(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        speak_mod.shutil,
        "which",
        lambda n: "/usr/bin/espeak-ng" if n == "espeak-ng" else None,
    )

    def raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="espeak-ng", timeout=30)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    assert speak("hello") is False
    err = capsys.readouterr().err
    assert "`espeak-ng` failed" in err


def test_speak_survives_pyttsx3_runtime_error(monkeypatch, capsys) -> None:
    """The classic CI failure: pyttsx3 imports, but init() raises because
    there's no audio device. Must be swallowed."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(speak_mod.shutil, "which", lambda _n: None)
    monkeypatch.setattr(speak_mod, "_pyttsx3_available", lambda: True)

    # Fake the pyttsx3 module so the backend function blows up on init().
    class FakePyttsx3:
        @staticmethod
        def init():
            raise RuntimeError("no audio device")

    monkeypatch.setitem(sys.modules, "pyttsx3", FakePyttsx3)
    assert speak("hello") is False
    err = capsys.readouterr().err
    assert "pyttsx3 failed" in err


def test_speak_succeeds_when_say_runs_cleanly(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(speak_mod.shutil, "which", lambda _n: "/usr/bin/say")
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert speak("two tags found") is True
    assert calls == [["say", "two tags found"]]


def test_speak_succeeds_when_espeak_runs_cleanly(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        speak_mod.shutil,
        "which",
        lambda n: "/usr/bin/espeak-ng" if n == "espeak-ng" else None,
    )
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert speak("hello") is True
    assert calls == [["espeak-ng", "hello"]]


# ---------------------------------------------------------------------------
# Dedup: repeated failures don't spam stderr
# ---------------------------------------------------------------------------


def test_warnings_are_deduplicated(monkeypatch, capsys) -> None:
    monkeypatch.setattr(speak_mod, "_choose_backend", lambda: None)
    speak("a")
    speak("b")
    speak("c")
    err = capsys.readouterr().err
    # The "no TTS backend" warning should appear exactly once across 3 calls.
    assert err.count("no TTS backend") == 1
