"""TTS wrapper — real voice output per ADR-001 accessibility contract.

Design (will be formalized in ADR-004, but the shape is decided):

Backends, in priority order:
    macOS   → `say`       (native, best quality, always present)
    Linux   → `espeak-ng` (native, packaged in most distros)
    Windows → `pyttsx3`   (last-resort fallback; uses SAPI under the hood)
    Any OS  → `pyttsx3`   if the native tool isn't on PATH

Voice is an **additive** channel. Plain text output to stdout is the
contract; speech is a convenience on top. If no backend is available, or
the audio device is missing, we emit a one-line stderr warning and return
False — we do **not** crash the CLI. Accessibility requirement per ADR-001.

Honest note: pyttsx3 is listed as fallback not ideal. Its default voices
are noticeably worse than `say` / `espeak-ng`, but it works offline on
Windows out of the box, which is the case we care about.
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def speak(text: str) -> bool:
    """Speak `text` aloud. Returns True iff a backend was invoked successfully.

    Contract:
        - Never raises. Ever. A missing TTS binary, a missing audio device,
          a pyttsx3 import error — all must become a quiet `False` return
          plus a single stderr warning (deduplicated across the process).
        - Empty / whitespace-only input is a no-op that returns False.
        - This function must never be the *only* channel for user-visible
          output. Callers print the text as well.
    """
    if not text or not text.strip():
        return False

    backend = _choose_backend()
    if backend is None:
        _warn_once(
            "voice: no TTS backend found "
            "(tried: `say`, `espeak-ng`, pyttsx3). "
            "Install one or run without --speak."
        )
        return False

    return backend(text)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _choose_backend():
    """Return a callable `(str) -> bool`, or None if nothing is available."""
    platform = sys.platform

    # Native first — better quality on macOS and Linux.
    if platform == "darwin" and shutil.which("say"):
        return _say_backend
    if platform.startswith("linux") and shutil.which("espeak-ng"):
        return _espeak_backend

    # Windows, or any platform where the native tool is missing.
    if _pyttsx3_available():
        return _pyttsx3_backend

    # Last chance: maybe `espeak-ng` is available outside Linux.
    if shutil.which("espeak-ng"):
        return _espeak_backend

    return None


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


def _say_backend(text: str) -> bool:
    """macOS native `say`. 30s timeout guards against pathological input."""
    try:
        subprocess.run(
            ["say", text],
            check=False,
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        _warn_once("voice: `say` failed to run — continuing without audio.")
        return False


def _espeak_backend(text: str) -> bool:
    """Linux / fallback `espeak-ng`. Same timeout contract as `say`."""
    try:
        subprocess.run(
            ["espeak-ng", text],
            check=False,
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        _warn_once(
            "voice: `espeak-ng` failed to run — continuing without audio."
        )
        return False


def _pyttsx3_available() -> bool:
    """Test-friendly probe — swallows any import-time error."""
    try:
        import pyttsx3  # noqa: F401
    except Exception:  # pragma: no cover — defensive
        return False
    return True


def _pyttsx3_backend(text: str) -> bool:
    """Windows (and fallback) backend. Wraps every call; never crashes."""
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception:
        # pyttsx3 can raise a zoo of errors: RuntimeError (no audio device),
        # OSError (missing driver), ImportError (broken install). Treat all
        # as soft failures — accessibility contract says never crash.
        _warn_once(
            "voice: pyttsx3 failed "
            "(no audio device, missing driver, or broken install)."
        )
        return False


# ---------------------------------------------------------------------------
# Deduplicated stderr warnings
# ---------------------------------------------------------------------------


_warned_keys: set[str] = set()


def _warn_once(msg: str) -> None:
    """Print `msg` to stderr exactly once per process. Avoids screaming
    in tight CLI loops if someone calls speak() many times on a broken box."""
    if msg in _warned_keys:
        return
    _warned_keys.add(msg)
    print(msg, file=sys.stderr)


def _reset_warnings() -> None:
    """Test helper — clears the dedup set so warnings re-emit in a new test."""
    _warned_keys.clear()
