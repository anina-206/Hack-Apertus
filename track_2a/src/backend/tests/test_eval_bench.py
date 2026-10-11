"""The eval benches (src/eval/) on the FHGR data, with the fake LLM from test_graph."""

import asyncio

import pytest

from backend.interview.prompts import CRITERIA
from backend.tests.test_graph import fake  # noqa: F401  (fixture)
from eval import bench_answers, bench_transcripts, checks, fhgr


def test_fhgr_data_loads():
    assert len(fhgr.answers()) == len(fhgr.annotations()) == 706
    assert len(fhgr.transcripts()) == 13  # the ones with reference feedback
    assert fhgr.phase_of("Q-01-01") == "intro" and fhgr.phase_of("Q-SIT-03") == "situational"
    assert fhgr.phase_of(None, 9) == "candidate_questions"
    occupation = fhgr.occupation({"name_de": "Konstrukteur/in EFZ", "occupation_id": "3699"})
    assert occupation["label"]["de"] == "Konstrukteur/in EFZ" and occupation["description"]


def test_sample_spreads_over_groups():
    picked = fhgr.sample(fhgr.answers(), 16, key=lambda a: a["lang"])
    assert len(picked) == 16 and {a["lang"] for a in picked} == {"de", "fr", "it", "gsw"}


def test_metrics():
    item = fhgr.compare_scores({"clarity": 3, "motivation": 2, "initiative": 4}, {"clarity": 3, "motivation": 4, "demeanor": 2})
    assert item["pairs"] == [(3, 3), (2, 4)] and item["gold_seen"] == 3 and item["both_seen"] == 2
    agreement = fhgr.score_agreement([item])
    assert agreement["mae"] == 1.0 and agreement["exact"] == 0.5 and agreement["coverage"] == 0.67
    assert fhgr.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0


@pytest.mark.parametrize("comment, language, problem", [
    ("Du hast dein Projekt gut erklärt.", "de", 0),
    ("Strukturieren Sie Ihre Antworten klarer.", "de", 2),
    ("Der Kandidat konnte konkrete Erfahrungen schildern.", "de", 1),
    ("Tu as bien expliqué ton projet.", "fr", 0),
    ("Vous avez bien expliqué votre projet.", "fr", 2),
])
def test_check_formal_address(comment, language, problem):
    report = {"criteria": [{"id": "clarity", "score": 3, "comment": comment, "evidence": ""}],
              "strengths": [], "improvements": []}
    assert checks.check_report(report, language)["formal_or_third_person"] == problem


def test_check_mojibake_empty_and_language():
    report = {"criteria": [{"id": "clarity", "score": 3, "comment": "", "evidence": ""},
                           {"id": "motivation", "score": 2, "comment": "Deine FreizeitaktivitÃ¤ten und du", "evidence": "x"}],
              "strengths": ["Du hast gut erklärt, wie du arbeitest."], "improvements": []}
    result = checks.check_report(report, "de")
    assert result["empty_comments"] == 1 and result["mojibake"] == 1 and result["wrong_language"] == 0
    assert checks.check_report(report, "it")["wrong_language"] == 1


def test_bench_answers_runs_with_fake_llm(fake):
    fake()
    result = asyncio.run(bench_answers.run(16, "pipeline", 2, log=lambda *_: None))  # one per language x class
    s = result["summary"]
    assert s["answers"] == 16 and s["parse_failed"] == 0 and s["avg_calls"] == 1
    assert s["scores"]["pairs"] > 0 and set(s["by_lang"]) == {"de", "fr", "it", "gsw"}


def test_bench_transcripts_runs_with_fake_llm(fake):
    client = fake()
    result = asyncio.run(bench_transcripts.run(["T-01"], 1, 2, use_judge=False, log=lambda *_: None))
    record = result["records"][0]
    assert record["analysis_calls"] == record["candidate_answers"] == 14 and record["report_calls"] == 1
    assert set(record["scores"]) == set(CRITERIA) and record["checks"]["empty_comments"] == 0
    assert client.calls.count("report") == 1 and result["summary"]["levels"]["pairs"] == 11


def test_bench_interviews_runs_a_scenario_through_the_api(fake, monkeypatch):
    from fastapi.testclient import TestClient

    from backend import config, main
    from backend.interview.graph import InterviewEngine
    from eval import bench_interviews
    from eval.run_interview import ScriptedCandidate

    fake()
    real_candidate = bench_interviews.ProfileCandidate
    monkeypatch.setattr(main, "engine", InterviewEngine())
    monkeypatch.setattr(bench_interviews, "ProfileCandidate", lambda profile, posting, language: ScriptedCandidate(language))
    client = TestClient(main.app, base_url="http://testserver/api/v1")
    record = bench_interviews.run_scenario(client, "S-01", log=lambda *_: None)
    assert record["posting_id"] == "P-01" and record["persona_level"] == 4 and len(record["success_criteria"]) == 5
    assert record["report"]["criteria"] and record["summary"]["gate_ok"]
    summary = bench_interviews.summarise([record])
    assert summary["interviews"] == 1 and summary["gate_ok"] and "judge" not in summary

    prompt = real_candidate._prompt(fhgr.candidates()["C-01"], config.postings()["P-01"], "de")
    assert "Luca" in prompt and "Plessur Maschinenbau AG" in prompt and "very good" in prompt
    assert bench_interviews.scenario_ids(None, ["apprenticeship_interview"], None)[:2] == ["S-01", "S-02"]
