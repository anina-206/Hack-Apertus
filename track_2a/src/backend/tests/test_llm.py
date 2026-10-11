import pytest

from backend.llm import fix_mojibake


@pytest.mark.parametrize("text, expected", [
    ("FreizeitaktivitÃ¤ten", "Freizeitaktivitäten"),
    ("Ã¼ber dich, trÃ¨s bien", "über dich, très bien"),
    ("Schon korrekt: Grüsse, très, città", "Schon korrekt: Grüsse, très, città"),
])
def test_fix_mojibake(text, expected):
    assert fix_mojibake(text) == expected
