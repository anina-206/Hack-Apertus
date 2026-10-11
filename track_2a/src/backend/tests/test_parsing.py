import json

import pytest

from backend.interview.parsing import JSONParseError, ReportDraft, parse_analysis, parse_json
from backend.interview.prompts import CRITERIA

SCORES = {key: 4 for key in CRITERIA}
VALID = json.dumps({"scores": SCORES, "short_tip": "Gut.", "follow_up": False})


@pytest.mark.parametrize("text", [
    VALID,
    f"Hier ist meine Bewertung:\n```json\n{VALID}\n```\nViel Erfolg!",
    f"<think>Let me consider {{the answer}}...</think>{VALID}",
    VALID[:-1] + ",}",                                   # trailing comma
    VALID.replace('"', "'").replace("false", "False"),  # Python-style dict
    VALID[:-1],                                          # truncated closing brace
])
def test_parses_messy_but_recoverable_output(text):
    result = parse_analysis(text)
    assert result.scores == SCORES
    assert result.follow_up is False


def test_normalises_keys_and_score_formats():
    raw = {
        "scores": {"Relevance": "4/5", "structure": 5.4, "Examples": {"score": 2},
                   "self-reflection": "3", "motivation": 9, "language": 0},
        "follow_up": "ja",
    }
    result = parse_analysis(json.dumps(raw))
    assert result.scores == {"relevance": 4, "structure": 5, "examples": 2,
                             "self_reflection": 3, "motivation": 5, "language": 1}
    assert result.follow_up is True


@pytest.mark.parametrize("text, error", [
    ("Die Antwort war gut.", "no JSON"),
    (json.dumps({"scores": {"relevance": 4}}), "missing scores"),
    (json.dumps({"scores": {**SCORES, "structure": "n/a"}}), "not a number"),
])
def test_rejects_unusable_output(text, error):
    with pytest.raises(JSONParseError, match=error):
        parse_analysis(text)


def test_report_draft_is_lenient_about_shape():
    raw = {
        "criteria": {"Examples": {"comment": "Gutes Beispiel.", "evidence": "PCs zusammen"}, "unknown": {}},
        "strengths": ["Sympathisch"],
        "improvements": ["Mehr Beispiele nennen."],
    }
    draft = parse_json(json.dumps(raw), ReportDraft)
    assert set(draft.criteria) == {"examples"}
    assert draft.improvements[0].tip == "Mehr Beispiele nennen." and draft.improvements[0].example_answer == ""


def test_report_draft_tolerates_missing_lists():
    # A cut-off answer may lack strengths or improvements: the report then falls back to the per-answer tips
    draft = parse_json(json.dumps({"criteria": {}}), ReportDraft)
    assert draft.strengths == [] and draft.improvements == []
