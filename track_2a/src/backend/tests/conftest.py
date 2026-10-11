"""Shared test setup."""

import os

# Tests never load Whisper or Piper models (the app's startup would otherwise preload them).
os.environ.setdefault("VOICE_PRELOAD", "false")
