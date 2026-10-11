"""The interview runner (src/eval/run_interview.py) against the app with a fake LLM."""

import json

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.interview.graph import InterviewEngine
from backend.tests.test_graph import fake  # noqa: F401  (fixture)
from eval import run_interview as runner


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "engine", InterviewEngine())
    return TestClient(main.app, base_url="http://testserver/api/v1")


@pytest.mark.parametrize("language", ["de", "fr", "it", "gsw"])
def test_scripted_interview_runs_to_the_end(fake, client, language):
    fake()
    run = runner.run_interview(client, language, "informatiker_efz", "friendly", "training", log=lambda *_: None)
    s = run["summary"]
    # 11 scored answers + an analysed candidate question + "no more questions"
    assert s["answers"] == 13 and s["follow_ups"] == 0
    assert s["llm_calls_total"] == 11 * 2 + 2 + 0 and s["llm_calls_avg"] == 1.85 and s["gate_ok"]
    assert run["turns"][-1]["phase"] == "candidate_questions" and run["report"]["criteria"]


def test_unknown_occupation_is_an_api_failure(fake, client):
    fake()
    with pytest.raises(runner.ApiFailure, match="unknown occupation"):
        runner.run_interview(client, "de", "astronaut", "friendly", "training", log=lambda *_: None)


def test_main_saves_the_run_and_returns_0(fake, client, monkeypatch, tmp_path, capsys):
    fake()
    monkeypatch.setattr(runner.httpx, "Client", lambda **_: client)
    out = tmp_path / "run.json"
    assert runner.main(["--language", "fr", "--out", str(out), "--quiet"]) == 0
    saved = json.loads(out.read_text())
    assert saved["language"] == "fr" and saved["candidate"] == "scripted" and saved["summary"]["gate_ok"]
    assert "Gate (avg < 5 calls per answer): OK" in capsys.readouterr().out


def test_main_reports_api_errors_with_exit_code_2(client, monkeypatch, capsys):
    for name in ("LLM_NAME", "LLM_BASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runner.httpx, "Client", lambda **_: client)
    assert runner.main(["--quiet", "--out", "/dev/null"]) == 2
    assert "LLM_UNAVAILABLE" in capsys.readouterr().err
