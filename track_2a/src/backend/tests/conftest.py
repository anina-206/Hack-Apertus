"""Shared test setup."""

import pytest

from backend.interview import graph


@pytest.fixture(autouse=True)
def no_automatic_follow_up(monkeypatch):
    """The short answers of the scripted tests should not trigger follow-ups; test_short_answers sets it back."""
    monkeypatch.setattr(graph, "SHORT_ANSWER_WORDS", 0)
