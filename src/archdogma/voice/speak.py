"""TTS wrapper — skeleton.

Design notes (will be finalized in ADR-004):
- Prefer native tools when available: `say` on macOS, `espeak-ng` on Linux.
  Reason: native voices sound noticeably better than pyttsx3 defaults.
- Fall back to pyttsx3 only when no native tool is found (Windows baseline).
- All output must also be available as plain text at the same time — voice
  is an additional channel, never the only one. Accessibility requirement.
"""

from __future__ import annotations


def speak(text: str) -> None:
    """Speak text aloud. Skeleton only."""
    raise NotImplementedError(
        "Voice output not implemented yet. See ADR-004 (pending)."
    )
