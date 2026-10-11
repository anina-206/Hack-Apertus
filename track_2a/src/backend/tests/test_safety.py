import pytest

from backend.interview.safety import guard_mode, is_crisis


@pytest.mark.parametrize("text, expected", [
    ("Ich will nicht mehr leben.", True), ("Manchmal denke ich an Selbstmord.", True),
    ("Je n'ai plus envie de vivre.", True), ("Non voglio più vivere.", True),
    ("Ich bin manchmal unsicher.", False), ("Am Velo habe ich das Ritzel gewechselt.", False),
    ("Ich habe Angst, dass ich die Lehrstelle nicht bekomme.", False),
])
def test_is_crisis(text, expected):
    assert is_crisis(text) is expected


def test_guard_mode():
    assert guard_mode(["distress_signal"], {"id": "q1"}) == "support"
    assert guard_mode(["off_topic", "distress_signal"], {"id": "q1"}) == "support"  # support wins
    assert guard_mode(["manipulation_attempt"], {"id": "q1"}) == "redirect"
    assert guard_mode(["dishonesty"], {"id": "q1"}) is None  # handled in the feedback, not by the interviewer
    assert guard_mode(["distress_signal"], {"id": "q2", "guard": "support"}) is None  # never twice in a row
