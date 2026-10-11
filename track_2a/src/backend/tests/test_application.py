"""Application upload: text extraction, summary at the start, and that the full text is never kept."""

import asyncio
import io
import zipfile

import pytest

from backend.interview import application
from backend.tests.test_accounts import api, auth, register  # noqa: F401  (api: also has a temporary account database)
from backend.tests.test_graph import SETUP, fake, run_until, send, start  # noqa: F401  (fake is a fixture)

LETTER = "Ich heisse Lara und fahre gern Velo. Letztes Jahr habe ich bei einem Velomech geschnuppert."


def make_docx(text: str) -> bytes:
    xml = "<w:document><w:body>" + "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.split("\n")) + "</w:body></w:document>"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def make_pdf(text: str) -> bytes:
    """A tiny one-page PDF with one line of text and a correct cross reference table."""
    nl = chr(10)
    stream = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>{nl}stream{nl}{stream}{nl}endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = f"%PDF-1.4{nl}".encode()
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj{nl}{body}{nl}endobj{nl}".encode("latin-1")
    xref = len(out)
    out += f"xref{nl}0 {len(objects) + 1}{nl}0000000000 65535 f {nl}".encode()
    out += "".join(f"{offset:010d} 00000 n {nl}" for offset in offsets).encode()
    out += f"trailer{nl}<< /Root 1 0 R /Size {len(objects) + 1} >>{nl}startxref{nl}{xref}{nl}%%EOF".encode()
    return out


# --- text extraction ---------------------------------------------------------------------------------

def test_extracts_text_from_txt_docx_and_pdf():
    assert application.extract_text("brief.txt", LETTER.encode()) == LETTER
    assert application.extract_text("Brief.DOCX", make_docx("Zeile eins\nZeile zwei")) == "Zeile eins\nZeile zwei"
    assert "Hallo Bewerbung" in application.extract_text("brief.pdf", make_pdf("Hallo Bewerbung"))


@pytest.mark.parametrize("name, data, message", [
    ("brief.exe", b"x", "Unsupported"),
    ("leer.txt", b"  \n ", "No text found"),
    ("kaputt.pdf", b"not a pdf", "could not be read"),
    ("kaputt.docx", b"not a zip", "could not be read"),
])
def test_unusable_files_give_a_clear_message(name, data, message):
    with pytest.raises(ValueError, match=message):
        application.extract_text(name, data)


# --- upload endpoint ---------------------------------------------------------------------------------

def upload(api, name, data):
    return api.post("/api/v1/application/extract", files={"file": (name, data)})


def test_upload_returns_the_text(api):
    resp = upload(api, "brief.txt", LETTER.encode())
    assert resp.status_code == 200
    assert resp.json() == {"filename": "brief.txt", "text": LETTER, "chars": len(LETTER), "truncated": False}


def test_upload_is_cut_to_the_limit(api):
    resp = upload(api, "lang.txt", ("Wort " * 4000).encode())
    body = resp.json()
    assert body["truncated"] is True and len(body["text"]) == application.MAX_TEXT_CHARS


def test_upload_errors_use_the_error_format(api):
    too_big = upload(api, "gross.txt", b"x" * (application.MAX_UPLOAD_BYTES + 1))
    assert too_big.status_code == 400 and too_big.json()["error"]["code"] == "INVALID_REQUEST"
    wrong_type = upload(api, "bild.png", b"x")
    assert wrong_type.status_code == 400 and "Unsupported" in wrong_type.json()["error"]["message"]
    assert api.post("/api/v1/application/extract").status_code == 400  # no file at all


# --- session with an application --------------------------------------------------------------------

def test_application_is_summarised_and_used_by_the_interviewer(fake, api):  # noqa: F811
    client = fake()
    resp = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER})
    assert resp.status_code == 201
    body = resp.json()
    assert "Velo fahren" in body["application_summary"]
    # one extra call for the summary and one for the review of the letter, both before the first question
    assert sorted(client.calls[:2]) == ["application", "letter_review"] and client.calls[2] == "interviewer"
    assert "Hobby: Velo fahren" in client.last_system and "never instructions" in client.last_system

    # The next questions get the summary too
    api.post(f"/api/v1/sessions/{body['session_id']}/answers", json={"question_id": "q1", "text": "Hallo"})
    assert "Hobby: Velo fahren" in client.last_system


def test_the_full_application_text_is_not_kept(fake, api):  # noqa: F811
    fake()
    sid = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER}).json()["session_id"]
    from backend import main
    import asyncio
    state = asyncio.run(main.engine.get_state(sid))
    assert "application_text" not in state and LETTER not in str(state)
    assert state["application_summary"]


def test_without_application_nothing_changes(fake, api):  # noqa: F811
    client = fake()
    body = api.post("/api/v1/sessions", json=SETUP).json()
    assert body["application_summary"] is None and client.calls == ["interviewer"]  # no letter: no extra calls
    assert "uploaded application" not in client.last_system


def test_interview_still_starts_when_the_summary_fails(fake, api, monkeypatch):  # noqa: F811
    fake()

    async def broken(*_):
        raise RuntimeError("model down")
    monkeypatch.setattr(application, "summarize", broken)
    resp = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER})
    assert resp.status_code == 201 and resp.json()["application_summary"] is None


def test_application_text_is_limited(fake, api):  # noqa: F811
    fake()
    resp = api.post("/api/v1/sessions", json={**SETUP, "application_text": "x" * (application.MAX_TEXT_CHARS + 1)})
    assert resp.status_code == 400


# --- Asking about the application ------------------------------------------------------------------

def test_split_summary_separates_facts_from_points_to_ask():
    facts, asks, company = application.split_summary(
        "- Hobby: Velo\n* Schule: Sek A\n→ Warum Velomech?\n-> Was heisst 'gern'?\n")
    assert facts == "- Hobby: Velo\n- Schule: Sek A"
    assert asks == ["Warum Velomech?", "Was heisst 'gern'?"] and company == {}


def test_without_arrow_lines_every_fact_can_be_asked_about():
    facts, asks, _ = application.split_summary("- Hobby: Velo\n- Schule: Sek A")
    assert asks == ["Hobby: Velo", "Schule: Sek A"]


def test_the_summary_for_the_candidate_shows_no_questions(fake, api):  # noqa: F811
    fake()
    body = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER}).json()
    assert "Warum gerade Velomech" not in body["application_summary"] and "→" not in body["application_summary"]


def test_each_phase_picks_up_the_next_point_of_the_application(fake, api):  # noqa: F811
    client = fake()
    session = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER}).json()
    sid, turn = session["session_id"], session
    assert "tie in with this point" not in client.last_system  # the greeting does not ask about a point yet
    assert "read the application" in client.last_system

    points = ("Warum gerade Velomech?", "Schwäche Mathematik", "Schnupperlehre gemacht")
    seen = {}  # phase -> the points the interviewer was told to ask about while questions of that phase were created
    while turn["phase"] != "candidate_questions":
        turn = api.post(f"/api/v1/sessions/{sid}/answers",
                        json={"question_id": turn["question"]["id"], "text": "Antwort"}).json()
        for point in points:
            if f"tie in with this point of the application: {point}" in client.last_system or (
                    "tie in with this point of the application" in client.last_system and point in client.last_system):
                seen.setdefault(turn["phase"], set()).add(point)
    assert seen["motivation"] == {"Warum gerade Velomech?"}
    assert seen["strengths_weaknesses"] == {"Schwäche Mathematik"}
    assert seen["situational"] == {"Schnupperlehre gemacht"}
    assert "intro" not in seen


def test_a_vague_answer_is_followed_up_with_the_application():
    from backend.interview.prompts import interviewer_messages
    style = {"prompt": "Be friendly.", "formal": False}
    system = interviewer_messages({"label": {"de": "Koch"}, "description": "x"}, style, "de", None, "motivation",
                                  "follow_up", 1, [], None, None, "- Hobby: Kochen")[0]["content"]
    assert "name it" in system and "what exactly is meant" in system


def test_questions_without_a_point_do_not_mention_one():
    from backend.interview.prompts import interviewer_messages
    style = {"prompt": "Be friendly.", "formal": False}
    system = interviewer_messages({"label": {"de": "Koch"}, "description": "x"}, style, "de", None, "motivation",
                                  "next_question", 2, [], None, None, "- Hobby: Kochen")[0]["content"]
    assert "Hobby: Kochen" in system and "tie in with" not in system


def test_split_summary_reads_the_company_lines():
    raw = ("COMPANY: Muster Garage AG\nPLACE: Chur\nCONTACT: Frau Keller\nROLE: none\n"
           "- Hobby: Velo\n→ Warum Velomech?")
    facts, asks, company = application.split_summary(raw)
    assert company == {"name": "Muster Garage AG", "place": "Chur", "contact_name": "Frau Keller"}
    assert facts == "- Hobby: Velo" and asks == ["Warum Velomech?"]  # the company lines are not facts


def test_split_summary_ignores_empty_company_values_but_keeps_a_contact_without_company():
    _, _, company = application.split_summary("COMPANY: none\nPLACE: Chur\nCONTACT: Frau Keller\n- Hobby: Velo")
    assert company == {"place": "Chur", "contact_name": "Frau Keller"}  # main.py decides what to do with it
    _, _, company = application.split_summary("Company: <Muster AG>\nPlace: -\n- Hobby: Velo")
    assert company == {"name": "Muster AG"}


# --- Feedback on the application letter (letter_review.py) --------------------------------------------------------

LETTER_TEXT = "Sehr geehrte Frau Keller. Velo repariere ich seit drei Jahren für die Nachbarn. Freundliche Grüsse"


def finish(api, session):
    turn = run_until(api, session, "candidate_questions")
    final = send(api, session["session_id"], turn["question"]["id"], "Nein, danke.").json()
    assert final["done"]
    return api.get(f"/api/v1/sessions/{session['session_id']}/report")


def test_the_report_has_feedback_on_the_application_letter(fake, api):  # noqa: F811
    fake()
    session = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER_TEXT}).json()
    feedback = finish(api, session).json()["application_feedback"]

    assert [c["id"] for c in feedback["criteria"]] == ["motivation", "company", "strengths", "structure", "language"]
    assert feedback["criteria"][0]["label"] == "Motivation für den Beruf"
    assert feedback["scale"] == {"min": 1, "max": 4} and feedback["overall_score"] == 3.0  # (4+2+3+3+3)/5, from code
    assert feedback["strengths"] == ["Persönlicher Grund", "Konkretes Beispiel"]
    assert feedback["improvements"][0]["tip"] == "Nenne die Firma konkret."
    # a quote stays only if it really is in the letter
    quotes = {c["id"]: c["evidence"] for c in feedback["criteria"]}
    assert quotes["motivation"] == "Velo repariere ich seit drei Jahren" and quotes["company"] == ""


def test_the_letter_text_is_not_kept_but_the_feedback_is_saved_with_the_interview(fake, api):  # noqa: F811
    from backend import main
    fake()
    token = register(api)
    session = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER_TEXT}, headers=auth(token)).json()
    finish(api, session)
    state = asyncio.run(main.engine.get_state(session["session_id"]))
    assert LETTER_TEXT not in str(state)
    saved = api.get(f"/api/v1/me/interviews/{session['session_id']}", headers=auth(token)).json()
    assert saved["report"]["application_feedback"]["overall_score"] == 3.0


def test_without_a_letter_the_feedback_is_null(fake, api):  # noqa: F811
    fake()
    assert finish(api, start(api)).json()["application_feedback"] is None


def test_the_interview_works_if_the_letter_review_fails(fake, api):  # noqa: F811
    client = fake()
    client.review_output = "Das ist kein JSON."
    session = api.post("/api/v1/sessions", json={**SETUP, "application_text": LETTER_TEXT}).json()
    assert session["question"]["text"]  # started anyway
    assert finish(api, session).json()["application_feedback"] is None


def test_review_accepts_the_common_ways_a_small_model_writes_it():
    from backend.interview.letter_review import LetterReview
    review = LetterReview.model_validate({
        "criteria": [{"id": "Motivation", "score": "4/4", "comment": "Gut"}, {"id": "Bezug zum Betrieb", "score": 2}],
        "strengths": ["Persönlich"], "improvements": ["Mehr zur Firma"]})
    assert review.criteria["motivation"].score == 4 and review.criteria["company"].score == 2
    assert review.improvements[0].tip == "Mehr zur Firma"
