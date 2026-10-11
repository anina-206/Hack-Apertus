"""Sessions survive a restart when the SQLite checkpointer is used (SESSIONS_DB)."""

from fastapi.testclient import TestClient

from backend import main
from backend.tests.test_graph import SETUP, fake  # noqa: F401  (fixture)


def test_session_survives_restart(fake, monkeypatch, tmp_path):
    fake()
    monkeypatch.setattr(main, "engine", main.engine)  # restored after the test (the lifespan replaces it)
    monkeypatch.setenv("SESSIONS_DB", str(tmp_path / "sessions.db"))

    with TestClient(main.app) as api:  # "with" runs the lifespan -> SQLite engine
        session = api.post("/api/v1/sessions", json=SETUP).json()
        api.post(f"/api/v1/sessions/{session['session_id']}/answers", json={"question_id": "q1", "text": "Ich bin Lara."})

    with TestClient(main.app) as api:  # a new app start reads the same file
        state = api.get(f"/api/v1/sessions/{session['session_id']}").json()
    assert state["current_question_id"] == "q2" and len(state["history"]) == 3


def test_without_sessions_db_the_engine_stays_in_memory(monkeypatch):
    monkeypatch.delenv("SESSIONS_DB", raising=False)
    before = main.engine
    with TestClient(main.app):
        assert main.engine is before
