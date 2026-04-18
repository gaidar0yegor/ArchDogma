"""Voice mode — TTS output for probe results.

ADR-004 (pending) will finalize the TTS backend choice and output shape.
v0.1 baseline: pyttsx3 cross-platform, with fallback to subprocess calls to
native `say` (macOS) / `espeak-ng` (Linux) / SAPI (Windows).
"""
