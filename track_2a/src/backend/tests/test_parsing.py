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
        "scores": {"Relevance": "3/4", "Klarheit": 3.6, "Examples": {"score": 2}, "self-reflection": "3",
                   "motivation": 9, "communication": 0, "initiative": None, "preparation": "n/a", "demeanor": "-"},
        "follow_up": "ja",
    }
    result = parse_analysis(json.dumps(raw))
    observed = {key: value for key, value in result.scores.items() if value is not None}
    assert observed == {"relevance": 3, "clarity": 4, "concrete_examples": 2, "self_reflection": 3,
                        "motivation": 4, "communication": 1}
    assert set(result.scores) == set(CRITERIA)  # left-out criteria are None (not observed)
    assert result.follow_up is True


@pytest.mark.parametrize("text, error", [
    ("Die Antwort war gut.", "no JSON"),
    (json.dumps({"scores": {key: None for key in CRITERIA}}), "no criterion scored"),
    (json.dumps({"scores": {**SCORES, "clarity": "gut"}}), "not a number"),
])
def test_rejects_unusable_output(text, error):
    with pytest.raises(JSONParseError, match=error):
        parse_analysis(text)


def test_report_draft_is_lenient_about_shape():
    raw = {
        "criteria": {"Concrete examples": {"comment": "Gutes Beispiel.", "evidence": "PCs zusammen"}, "unknown": {}},
        "strengths": ["Sympathisch"],
        "improvements": ["Mehr Beispiele nennen."],
    }
    draft = parse_json(json.dumps(raw), ReportDraft)
    assert set(draft.criteria) == {"concrete_examples"}
    assert draft.improvements[0].tip == "Mehr Beispiele nennen." and draft.improvements[0].example_answer == ""


def test_report_draft_tolerates_missing_lists():
    # A cut-off answer may lack strengths or improvements: the report then falls back to the per-answer tips
    draft = parse_json(json.dumps({"criteria": {}}), ReportDraft)
    assert draft.strengths == [] and draft.improvements == []


@pytest.mark.parametrize("criteria", [
    {key: f"Text {key}." for key in CRITERIA},                                        # plain strings
    {"Klarheit": {"comment": "Text clarity."}, "Relevanz": "Text relevance.",          # labels as keys
     "Motivation": "Text motivation.", "Selbstreflexion": {"reason": "Text self_reflection."},
     "Kommunikationsfähigkeit": "Text communication.", "Konkrete Beispiele": {"text": "Text concrete_examples."},
     "Auftreten & Wirkung": "Text demeanor.", "Vorbereitung / Betriebskenntnis": "Text preparation.",
     "Zielorientierung": "Text goal_orientation.", "Umgang mit schwierigen Fragen": "Text difficult_questions.",
     "Eigeninitiative": "Text initiative."},
    [{"id": key, "comment": f"Text {key}."} for key in CRITERIA],                     # list of objects
    [{"criterion": key, "comment": f"Text {key}."} for key in CRITERIA],
])
def test_report_draft_accepts_common_criteria_shapes(criteria):
    raw = {"criteria": criteria, "strengths": ["x"], "improvements": ["y"]}
    draft = parse_json(json.dumps(raw), ReportDraft)
    assert {key: note.comment for key, note in draft.criteria.items()} == {key: f"Text {key}." for key in CRITERIA}


def test_report_draft_accepts_french_labels():
    raw = {"criteria": {"Pertinence": "Bien.", "Réflexion sur soi": "Honnête."}, "strengths": ["x"], "improvements": ["y"]}
    draft = parse_json(json.dumps(raw), ReportDraft)
    assert set(draft.criteria) == {"relevance", "self_reflection"}


def test_problem_flags_keep_only_known_values():
    raw = {"scores": SCORES, "problem_flags": ["Distress signal", "made_up", "off-topic", "distress_signal"]}
    assert parse_analysis(json.dumps(raw)).problem_flags == ["distress_signal", "off_topic"]
    assert parse_analysis(json.dumps({"scores": SCORES, "problem_flags": "manipulation_attempt"})).problem_flags == \
        ["manipulation_attempt"]
    assert parse_analysis(VALID).problem_flags == []
def test_report_draft_tolerates_missing_lists():
    # A cut-off answer may lack strengths or improvements: the report then falls back to the per-answer tips
    draft = parse_json(json.dumps({"criteria": {}}), ReportDraft)
    assert draft.strengths == [] and draft.improvements == []


def test_german_quotation_marks_inside_strings_are_kept():
    text = json.dumps({"strengths": ["Du hast „Lego Technic“ erwähnt."], "closing": "Weiter so."}, ensure_ascii=False)
    assert parse_json(text, ReportDraft).strengths == ["Du hast „Lego Technic“ erwähnt."]


def test_curly_quotes_used_as_json_quotes_still_parse():
    assert parse_json('{“closing”: “Weiter so.”}', ReportDraft).closing == "Weiter so."


def test_unescaped_quotes_and_line_breaks_inside_strings_are_repaired():
    text = ('{"strengths": ["Du hast gesagt: "Ich baue gerne Lego" und das passt."],\n'
            ' "closing": "Weiter so.\nDas war ein Training."}')
    draft = parse_json(text, ReportDraft)
    assert draft.strengths == ['Du hast gesagt: "Ich baue gerne Lego" und das passt.']
    assert draft.closing == "Weiter so.\nDas war ein Training."
