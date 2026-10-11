import pytest

from backend.interview.phases import (
    MAX_CANDIDATE_TURNS, PHASE_ORDER, QUESTIONS_PER_PHASE, TOTAL_QUESTIONS, Position, has_no_more_questions, is_courtesy,
    next_step, progress,
)


def at(phase, question=1, follow_ups=0):
    return Position(PHASE_ORDER.index(phase), question, follow_ups)


def test_walks_all_phases_in_order_without_follow_ups():
    pos, phases = Position(), []
    while pos.phase != "closing":
        phases.append(pos.phase)
        pos, _ = next_step(pos, "Eine Antwort.", wants_follow_up=False)
    expected = [p for p, n in QUESTIONS_PER_PHASE.items() for _ in range(n)] + ["candidate_questions"] * MAX_CANDIDATE_TURNS
    assert phases == expected


@pytest.mark.parametrize("pos, follow_up, expected, mode", [
    (at("motivation"), True, at("motivation", 1, 1), "follow_up"),
    (at("motivation", 1, 1), True, at("motivation", 2, 1), "next_question"),   # max one follow-up per phase
    (at("motivation", 3), False, at("strengths_weaknesses"), "new_phase"),
    (at("situational", 3, 1), True, at("candidate_questions"), "new_phase"),
])
def test_scored_phase_transitions(pos, follow_up, expected, mode):
    assert next_step(pos, "Antwort", follow_up) == (expected, mode)


@pytest.mark.parametrize("answer, pos, mode", [
    ("Wie gross ist das Team?", at("candidate_questions"), "answer_candidate"),
    ("Nein, danke.", at("candidate_questions"), "close"),
    ("Wie sieht der Einarbeitungsplan aus?", at("candidate_questions", MAX_CANDIDATE_TURNS), "answer_and_close"),
])
def test_candidate_questions(answer, pos, mode):
    assert next_step(pos, answer, wants_follow_up=True)[1] == mode


@pytest.mark.parametrize("answer, expected", [
    ("Nein, danke.", True),
    ("Nei, merci vielmal", True),
    ("Non, merci.", True),
    ("No, grazie, nessuna domanda.", True),
    ("Gibt es keine Probezeit?", False),
    ("Ich habe keine Frage zum Lohn, aber wie ist das Team organisiert und wer ist mein Ansprechpartner", False),
])
def test_has_no_more_questions(answer, expected):
    assert has_no_more_questions(answer) is expected


def test_progress_counts_main_questions_only():
    assert progress(Position()) == {"current": 1, "total": TOTAL_QUESTIONS}
    assert progress(at("motivation", 2, 1))["current"] == 4          # 2 intro + 2nd motivation; follow-ups don't count
    assert progress(at("candidate_questions", 2))["current"] == TOTAL_QUESTIONS
    assert progress(at("closing"))["current"] == TOTAL_QUESTIONS == 12


@pytest.mark.parametrize("answer, expected", [
    ("Danke!", True), ("Vielen Dank.", True), ("Merci vielmal", True), ("Merci beaucoup !", True),
    ("Grazie mille", True), ("ok", True), ("Vielen Dank für das Gespräch!", True),
    ("Danke, ich mag Informatik, weil ich gerne PCs baue.", False), ("Weiss nicht", False),
])
def test_is_courtesy(answer, expected):
    assert is_courtesy(answer) is expected
