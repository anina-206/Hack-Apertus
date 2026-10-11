"""Shared test setup."""

import os

import pytest

from backend.interview import graph

# Tests never load Whisper or Piper models (the app's startup would otherwise preload them).
os.environ.setdefault("VOICE_PRELOAD", "false")


@pytest.fixture(autouse=True)
def no_automatic_follow_up(monkeypatch):
    """The short answers of the scripted tests should not trigger follow-ups; test_short_answers sets it back."""
    monkeypatch.setattr(graph, "SHORT_ANSWER_WORDS", 0)
