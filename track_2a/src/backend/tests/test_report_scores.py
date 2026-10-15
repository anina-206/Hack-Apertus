"""Final report scores: calibrated against the FHGR expert annotations (2026-10-16)."""

from backend.interview import examples, rubric
from backend.interview.prompts import report_messages
from backend.interview.report import counts_for, final_scores


def test_every_challenge_criterion_is_a_focus_of_a_scored_phase():
    # docs/challenge.md: clarity, relevance, motivation, self-awareness, communication, concrete examples
    scored = ("intro", "motivation", "strengths_weaknesses", "situational")
    for key in rubric.TASK_CRITERIA:
        assert key in rubric.criteria(), key
        assert any(key in rubric.PHASE_FOCUS[phase] for phase in scored), key
    # communication had only the two intro questions; now also the situational ones
    assert "communication" in rubric.PHASE_FOCUS["situational"]


def test_a_mean_of_x_point_5_rounds_up():
    assert [rubric.clamp(v) for v in (1.4, 1.5, 2.5, 3.5, 3.6, 0.2, 4.7)] == [1, 2, 3, 4, 4, 1, 4]


def test_a_low_score_only_counts_where_the_phase_asks_for_the_criterion():
    assert not counts_for("concrete_examples", 1, "intro")  # a greeting is no place for examples
    assert counts_for("concrete_examples", 1, "situational")
    assert counts_for("concrete_examples", 3, "intro")  # good evidence counts everywhere
    assert counts_for("communication", 2, "situational")
    assert counts_for("motivation", 2, None)  # unknown phase: counted as before


def test_final_scores_leave_out_low_scores_outside_the_focus():
    state = {"done": True, "transcript": [], "analyses": [
        {"phase": "intro", "scores": {"clarity": 3, "concrete_examples": 1, "communication": 3}},
        {"phase": "motivation", "scores": {"motivation": 3, "relevance": 2, "concrete_examples": 1}},
        {"phase": "situational", "scores": {"concrete_examples": 3, "clarity": 2}},
        {"phase": "strengths_weaknesses", "scores": {"self_reflection": 3, "concrete_examples": 2}},
    ]}
    scores, means = final_scores(state)
    assert means["concrete_examples"] == 2.5 and scores["concrete_examples"] == 3  # the two 1s were off topic
    assert scores["clarity"] == 3 and scores["relevance"] == 2  # 2.5 -> 3; relevance is asked in motivation


def test_the_report_prompt_has_no_example_facts_it_could_copy():
    # FHGR feedback examples in this prompt were copied into real reports (Handball, bench T-14)
    system = report_messages({"label": {"de": "Koch"}, "description": "x"}, "fr", {"clarity": 3}, [], [])[0]["content"]
    assert "Handball" not in system and "3D-Drucker" not in system and "Write all texts in French" in system


def test_the_new_calibration_examples_are_in_the_analysis_prompt():
    text = examples.analysis_examples()
    assert "Materialliste" in text and "concrete_examples 4" in text
