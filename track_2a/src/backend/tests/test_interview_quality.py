"""Fixes from a real spoken test interview (Anlagen- und Apparatebauer/in, 2026-10-11).

The sentences below are taken from that interview's transcript.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.interview.graph import _drop_goodbye, _drop_praise
from backend import llm
from backend.interview.parsing import ReportDraft
from backend.interview.prompts import CRITERIA, analysis_messages, interviewer_messages
from backend.interview.report import _FIRST_PERSON, _in_third_person
from backend.interview.safety import guard_mode, is_meta, with_meta
from backend.voice.stt import vocabulary_hint
from backend.tests.test_graph import SETUP, api, fake, report_json, run_until, send, start  # noqa: F401  (fixtures)


# --- Praise before every question --------------------------------------------------------------------

@pytest.mark.parametrize("text, language, expected", [
    ("Das klingt super! Sport und Kultur sind tolle Hobbys. Was genau interessiert dich am meisten an deinen Hobbys?",
     "de", "Danke. Sport und Kultur sind tolle Hobbys. Was genau interessiert dich am meisten an deinen Hobbys?"),
    ("Das hört sich wirklich nach einer tollen Entscheidung an! Es ist schön, dass du den Beruf schon dreimal "
     "geschnuppert hast. Was genau hat dir am meisten gefallen?",
     "de", "Danke. Was genau hat dir am meisten gefallen?"),
    ("Das ist korrekt, in der Schweiz sagt man \"auswühlen\". Was macht dir am meisten Spass?",
     "de", "Danke. Was macht dir am meisten Spass?"),
    ("C'est super ! Qu'est-ce qui t'intéresse le plus ?", "fr", "Merci. Qu'est-ce qui t'intéresse le plus ?"),
    ("Che bello! Cosa ti piace di più?", "it", "Grazie. Cosa ti piace di più?"),
])
def test_praise_at_the_start_is_cut(text, language, expected):
    assert _drop_praise(text, language, 0) == expected


@pytest.mark.parametrize("text", [
    "Erzähl mir etwas über deine Lieblingsfächer.",
    "Das klingt super!",  # nothing would be left
    "Wie würdest du deinen Arbeitsplatz organisieren?",  # nothing to cut
    "In deiner Bewerbung steht, dass du Fussball spielst. Was lernst du dabei?",
])
def test_texts_without_praise_or_without_a_question_stay(text):
    assert _drop_praise(text, "de", 0) == text


def test_a_question_without_question_mark_also_loses_the_praise():
    text = ("Das ist ein sehr guter Punkt! Du hast bereits praktische Erfahrung mit Metallbearbeitung. "
            "Erzähl mir jetzt etwas darüber, was du noch lernen könntest.")
    assert _drop_praise(text, "de", 0) == ("Danke. Du hast bereits praktische Erfahrung mit Metallbearbeitung. "
                                           "Erzähl mir jetzt etwas darüber, was du noch lernen könntest.")


def test_praise_after_a_neutral_word_is_cut_too():
    # Seen in a probe with FHGR answers (2026-10-15): the model put the praise after "Okay,"
    assert _drop_praise("Okay, das klingt nach einem guten Plan. Was weisst du über die Firma?", "de", 1) == \
        "Okay. Was weisst du über die Firma?"
    assert _drop_praise("Okay, in der Bäckerei also. Was hat dir gefallen?", "de", 1) == \
        "Okay, in der Bäckerei also. Was hat dir gefallen?"  # picking up a detail is not praise
    for judging in ("Okay, einen klaren Plan zu haben und bei Bedarf Hilfe zu holen, das klingt gut.",
                    "Okay, das verantwortungsvolle Vorgehen gefällt mir.",
                    "Okay, das Sicherheitsbewusstsein auch bei anderen zu fördern, ist wichtig."):
        assert _drop_praise(f"{judging} Was weisst du über die Firma?", "de", 1) == "Okay. Was weisst du über die Firma?"


# --- Compliments only for really good answers ----------------------------------------------------------

def test_the_quality_of_an_answer_comes_from_its_scores():
    from backend.interview.graph import answer_quality
    assert answer_quality({"scores": {"clarity": 4, "motivation": 3, "relevance": 3, "demeanor": None}}) == "strong"
    # Level-3 answers of the FHGR data: mostly 3s, the model wants no follow-up -> good
    level3 = {"clarity": 3, "relevance": 3, "motivation": 2, "concrete_examples": 2}
    assert answer_quality({"scores": level3, "follow_up": False}) == "good"
    assert answer_quality({"scores": level3, "follow_up": True}) == "okay"  # still something missing
    assert answer_quality({"scores": {"clarity": 3, "motivation": 3, "relevance": 3}, "follow_up": True}) == "good"  # mean 3
    assert answer_quality({"scores": {"clarity": 4, "motivation": 4, "concrete_examples": 1}, "follow_up": True}) == "good"
    assert answer_quality({"scores": {"clarity": 2, "motivation": 1, "concrete_examples": 1}, "follow_up": True}) == "weak"
    assert answer_quality({"scores": {"clarity": None}}) is None and answer_quality(None) is None


def test_random_text_is_no_real_answer_but_i_dont_know_is():
    from backend.interview.graph import _no_real_answer
    assert _no_real_answer({"scores": {"clarity": 1, "relevance": 1, "motivation": 1}}, "asdf jklö qwertz")
    assert _no_real_answer({"scores": {"clarity": 2, "relevance": 1}}, "blabla")
    assert not _no_real_answer({"scores": {"clarity": 2, "relevance": 1}}, "Ich weiss nicht.")  # honest, scored
    # A real but weak answer (FHGR level 2) with relevance 1 stays a scored answer
    assert not _no_real_answer({"scores": {"clarity": 2, "relevance": 1, "motivation": 1}},
                               "Mit den Tieren spielen und sie füttern. Und halt schauen, dass es ihnen gut geht.")
    assert not _no_real_answer({"scores": {"clarity": 1, "relevance": 3}}, "asdf")  # relevant: not nonsense


def test_random_text_gets_a_clarify_question_and_no_scores(fake, api):
    nonsense = json.dumps({"scores": {"clarity": 1, "relevance": 1, "motivation": 1}, "short_tip": "Sag mehr.",
                           "follow_up": True, "problem_flags": []})
    client = fake(analysis_outputs=[nonsense], interviewer_outputs=["Erste Frage?", "Das habe ich nicht verstanden. Wie heisst du?"])
    session = start(api)
    body = send(api, session["session_id"], "q1", "asdf jklö qwertz").json()
    assert "did not understand the ANSWER" in client.last_interviewer_system
    assert body["question"]["text"].startswith("Das habe ich nicht verstanden")
    assert not body.get("turn_feedback") or not any((body["turn_feedback"].get("scores") or {}).values())


def test_the_tip_says_stark_only_for_a_strong_answer():
    from backend.interview.graph import _honest_tip
    tip = "Stark: Deine Mutter hat dir einen praktischen Grund genannt. Ergänze, was dir gefällt."
    assert _honest_tip(tip, "okay") == "Deine Mutter hat dir einen praktischen Grund genannt. Ergänze, was dir gefällt."
    assert _honest_tip(tip, "strong") == tip and _honest_tip(tip, "good") == tip
    assert _honest_tip("Super! du hast gut geplant.", "weak") == "Du hast gut geplant."
    assert _honest_tip("Erkläre konkret, was du tun würdest.", "weak") == "Erkläre konkret, was du tun würdest."


def test_the_interviewer_is_told_how_to_react_to_the_last_answer():
    occupation, style = {"label": {"de": "Koch"}, "description": "x"}, {"prompt": "Be friendly.", "formal": False}

    def system(quality):
        return interviewer_messages(occupation, style, "de", None, "motivation", "next_question", 2, [],
                                    quality=quality)[0]["content"]
    assert "was really good" in system("strong") and "names exactly what was good" in system("strong")
    assert "was good. Start with a short, positive reaction" in system("good")
    assert "do not praise it" in system("okay").lower() and "do not praise it" in system("weak").lower()
    assert "Do not praise, evaluate or comment" in system(None)  # no analysis (e.g. the opening): neutral


def test_a_strong_answer_keeps_the_interviewers_compliment(fake, api):
    compliment = "Das zeigt gut, wie genau du arbeitest. Was weisst du über unseren Betrieb?"
    strong = json.dumps({"scores": {"clarity": 4, "relevance": 4, "motivation": 3}, "short_tip": "Stark: gutes Beispiel.",
                         "follow_up": False, "problem_flags": []})
    client = fake(analysis_outputs=[strong], interviewer_outputs=["Erste Frage?", compliment])
    session = start(api)
    answer = "Ich habe in der Schnupperlehre einen kleinen Hocker gebaut und dabei gelernt, genau zu messen und zu schleifen."
    body = send(api, session["session_id"], "q1", answer).json()
    assert body["question"]["text"] == compliment and "was really good" in client.last_interviewer_system
    assert body["turn_feedback"]["short_tip"] == "Stark: gutes Beispiel."


def test_an_okay_answer_loses_the_interviewers_compliment_and_the_stark(fake, api):
    okay = json.dumps({"scores": {"clarity": 3, "relevance": 2, "motivation": 2}, "short_tip": "Stark: guter Grund. Sag mehr.",
                       "follow_up": False, "problem_flags": []})
    fake(analysis_outputs=[okay], interviewer_outputs=["Erste Frage?", "Das klingt super! Was weisst du über uns?"])
    session = start(api)
    answer = "Meine Mutter hat gesagt, dass das ein guter Beruf ist, und ich arbeite gern mit Holz im Werken in der Schule."
    body = send(api, session["session_id"], "q1", answer).json()
    assert not body["question"]["text"].startswith("Das klingt super") and body["question"]["text"].endswith("über uns?")
    assert body["turn_feedback"]["short_tip"] == "Guter Grund. Sag mehr."


def test_the_neutral_word_changes_from_turn_to_turn():
    starts = {_drop_praise("Das klingt super! Was machst du gern?", "de", turn).split()[0] for turn in range(3)}
    assert starts == {"Danke.", "Okay.", "Verstehe."}


# --- Double goodbye -----------------------------------------------------------------------------------

def test_the_models_own_goodbye_is_cut_before_the_fixed_one():
    text = ("Bei uns steht die Unterstützung der Lernenden im Vordergrund. Vielen Dank für dein Kommen und die "
            "offenen Fragen! Es war eine Freude, dich kennenzulernen. Bis bald!")
    assert _drop_goodbye(text) == "Bei uns steht die Unterstützung der Lernenden im Vordergrund."
    assert _drop_goodbye("Bis bald!") == "Bis bald!"  # never empty
    # A goodbye-like sentence inside the answer is part of the answer
    answer = "Wir melden uns bis Ende Monat. Die Lehre dauert vier Jahre."
    assert _drop_goodbye(answer) == answer


def test_a_long_spoken_no_ends_the_interview_without_analysis_and_with_one_goodbye(fake, api):
    client = fake()
    session = start(api)
    turn = run_until(api, session, "candidate_questions")
    turn = send(api, session["session_id"], turn["question"]["id"],
                "wie sieht bei euch die lehrlingsunterstützung aus und wie viele Ferien hat man").json()
    calls = len(client.calls)
    turn = send(api, session["session_id"], turn["question"]["id"],
                "nein danke das wäre es meinerseits gewesen vielen Dank fürs Gespräch").json()
    assert turn["done"] and len(client.calls) == calls  # fixed goodbye, nothing scored
    assert turn["closing_message"].count("Vielen Dank") == 1


# --- Swiss spelling ------------------------------------------------------------------------------------

def test_no_sharp_s_in_llm_texts(monkeypatch):
    async def create(**_):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Das macht Spaß, weißt du?"))],
                               usage=None)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "_get_client", lambda: (client, "fake-model"))
    assert asyncio.run(llm.chat_completion([])) == "Das macht Spass, weisst du?"


# --- Questions about the interview itself / garbled speech -----------------------------------------------

def test_a_short_question_about_dialect_is_meta():
    assert is_meta("ist das thun auswühlen geht auch auf schweizerdeutsch")
    assert is_meta("Kannst du die Frage nochmal wiederholen")
    assert not is_meta("Ich rede zu Hause Mundart und spiele gerne Fussball, und in der Schule mag ich Werken "
                       "und Mathematik, weil ich gerne rechne")  # a real (long) answer
    assert with_meta([], "Darf ich Mundart reden") == ["unclear_or_meta"]


def test_clarify_has_the_lowest_priority_and_comes_once():
    assert guard_mode(["unclear_or_meta"], {"id": "q1"}) == "clarify"
    assert guard_mode(["unclear_or_meta", "distress_signal"], {"id": "q1"}) == "support"
    assert guard_mode(["unclear_or_meta"], {"id": "q2", "guard": "clarify"}) is None


def test_a_meta_question_gets_a_clarify_turn_and_is_not_scored(fake, api):
    client = fake()
    session = start(api)
    body = send(api, session["session_id"], "q1", "ist das thun auswühlen geht auch auf schweizerdeutsch").json()
    assert body["question"]["guard"] == "clarify" and body["progress"]["current"] == 1
    assert "Never guess what it meant" in client.last_interviewer_system
    assert body["turn_feedback"]["short_tip"] == ""
    assert all(score is None for score in body["turn_feedback"]["scores"].values())


# --- Prompts -----------------------------------------------------------------------------------------------

OCCUPATION = {"label": {"de": "Anlagen- und Apparatebauer/in EFZ"}, "description": "Baut Anlagen."}
STYLE = {"prompt": "Be friendly.", "formal": False}


def test_the_goal_of_the_question_comes_last_in_the_interviewer_prompt():
    system = interviewer_messages(OCCUPATION, STYLE, "de", None, "motivation", "next_question", 2, [])[0]["content"]
    assert system.rstrip().endswith("do not ask again about the candidate's last answer.")
    assert "Why did they apply at this company?" in system.split("YOUR TASK NOW:")[1]
    assert "Do not praise" in system


def test_without_a_posting_candidate_questions_get_general_apprenticeship_facts():
    system = interviewer_messages(OCCUPATION, STYLE, "de", None, "candidate_questions", "answer_candidate", 1,
                                  [])[0]["content"]
    assert "5 weeks" in system and "never tell the candidate to ask somewhere else" in system
    assert "never invent facts about this company" in system


def test_the_analysis_sees_earlier_tips_and_the_calibration():
    tips = ("Erwähne konkrete Beispiele.", "Verbinde dein Hobby mit dem Beruf.")
    system = analysis_messages(OCCUPATION, "de", "intro", "Frage?", "Antwort", previous_tips=tips)[0]["content"]
    assert all(tip in system for tip in tips) and "concrete_examples at least 3" in system
    assert "Tips the candidate already got" not in analysis_messages(OCCUPATION, "de", "intro", "F?", "A")[0]["content"]


# --- Report ------------------------------------------------------------------------------------------------

def draft(strength):
    return ReportDraft(strengths=[strength], criteria={}, improvements=[], closing="")


def test_third_person_is_recognised():
    assert _in_third_person(draft("Der Kandidat verknüpft seine sportlichen Aktivitäten mit dem Beruf."))
    assert _in_third_person(draft("Gute Antwort. Er zeigt ein echtes Interesse."))
    assert not _in_third_person(draft("Du verknüpfst deine sportlichen Aktivitäten mit dem Beruf."))


def test_example_answers_must_be_in_the_first_person():
    assert _FIRST_PERSON.search("Beim Messen der Bratpfanne war der Henkel schief, daran arbeite ich.")
    assert not _FIRST_PERSON.search("Dein aktueller Handwerkunterricht wird nicht näher ausgeführt.")


def test_an_italian_example_answer_without_pronoun_is_kept(fake, api):
    report = json.loads(report_json())
    report["improvements"] = [{"tip": "Racconta di più.", "example_answer": "Ho fatto uno stage di tre giorni."}]
    fake(report_outputs=[json.dumps(report)])
    session = start(api, language="it")
    turn = run_until(api, session, "candidate_questions", "Mi piace montare i computer.")
    send(api, session["session_id"], turn["question"]["id"], "No, grazie.")
    feedback = api.get(f"/api/v1/sessions/{session['session_id']}/report").json()
    assert feedback["improvements"][0]["example_answer"] == "Ho fatto uno stage di tre giorni."


def test_a_third_person_report_is_written_again(fake, api):
    third = json.loads(report_json())
    third["strengths"] = ["Der Kandidat zeigt Interesse."]
    third["improvements"] = [{"tip": "Mehr Details.", "example_answer": "Dein Unterricht wird nicht ausgeführt."}]
    client = fake(report_outputs=[json.dumps(third), report_json()])
    session = start(api)
    turn = run_until(api, session, "candidate_questions")
    send(api, session["session_id"], turn["question"]["id"], "Nein, danke.")
    report = api.get(f"/api/v1/sessions/{session['session_id']}/report").json()
    assert client.calls.count("report") == 2 and report["strengths"] == ["Sympathischer Einstieg"]


def test_a_description_instead_of_an_example_answer_is_dropped(fake, api):
    out = json.loads(report_json())
    out["improvements"] = [{"tip": "Mehr Details.", "example_answer": "Dein Unterricht wird nicht ausgeführt."}]
    fake(report_outputs=[json.dumps(out)])
    session = start(api)
    turn = run_until(api, session, "candidate_questions")
    send(api, session["session_id"], turn["question"]["id"], "Nein, danke.")
    report = api.get(f"/api/v1/sessions/{session['session_id']}/report").json()
    assert report["improvements"] == [{"tip": "Mehr Details.", "example_answer": ""}]


# --- Whisper hint ------------------------------------------------------------------------------------------

def test_whisper_gets_occupation_and_company():
    assert vocabulary_hint("gsw", "Anlagen- und Apparatebauer/in", "Bühler AG") == (
        "Bewerbungsgespräch für eine Lehrstelle als Anlagen- und Apparatebauer/in bei Bühler AG. "
        "Schnupperlehre, Lehrbetrieb, Berufsschule, Lernende.")
    assert vocabulary_hint("fr", "Informaticien CFC").startswith("Entretien d'embauche pour un apprentissage de "
                                                                 "Informaticien CFC.")
    assert vocabulary_hint("de", "") == ""
