"""Accounts and saved interviews (docs/api.md section 3b), against a fake LLM and a temporary database."""

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.accounts import Store
from backend.interview.graph import InterviewEngine
from backend.tests.test_graph import SETUP, fake, run_until, send, start  # noqa: F401  (fake is a fixture)

CREDS = {"username": "Lara", "password": "geheim1234"}


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "engine", InterviewEngine())
    monkeypatch.setattr(main, "store", Store(str(tmp_path / "test.db")))
    return TestClient(main.app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register(api, **overrides):
    resp = api.post("/api/v1/auth/register", json={**CREDS, **overrides})
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


def test_register_login_logout(api):
    token = register(api)
    me = api.get("/api/v1/auth/me", headers=auth(token))
    assert me.json()["username"] == "Lara"

    # The username is not case-sensitive, a second registration is refused
    dup = api.post("/api/v1/auth/register", json={**CREDS, "username": "lara"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "USERNAME_TAKEN"

    login = api.post("/api/v1/auth/login", json={"username": "LARA", "password": CREDS["password"]})
    assert login.status_code == 200
    assert api.post("/api/v1/auth/logout", headers=auth(token)).status_code == 204
    assert api.get("/api/v1/auth/me", headers=auth(token)).status_code == 401


def test_wrong_password_and_unknown_user_look_the_same(api):
    register(api)
    for creds in ({**CREDS, "password": "falsch12345"}, {"username": "nobody", "password": "geheim1234"}):
        resp = api.post("/api/v1/auth/login", json=creds)
        assert resp.status_code == 401 and resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_input_is_validated(api):
    assert api.post("/api/v1/auth/register", json={"username": "ab", "password": "geheim1234"}).status_code == 400
    assert api.post("/api/v1/auth/register", json={"username": "lara", "password": "kurz"}).status_code == 400
    assert api.get("/api/v1/me/interviews").json()["error"]["code"] == "UNAUTHORIZED"


def test_passwords_are_not_stored_in_clear(api):
    register(api)
    with main.store._db() as db:
        stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert CREDS["password"] not in stored


def test_whole_interview_is_saved_for_the_user(fake, api):  # noqa: F811
    fake()
    token = register(api)
    session = api.post("/api/v1/sessions", json=SETUP, headers=auth(token)).json()
    sid = session["session_id"]

    # Saved right after the start
    listed = api.get("/api/v1/me/interviews", headers=auth(token)).json()["interviews"]
    assert [i["session_id"] for i in listed] == [sid] and listed[0]["done"] is False

    turn = run_until(api, session, "candidate_questions")
    final = send(api, sid, turn["question"]["id"], "Nein, danke.").json()
    assert final["done"] is True
    assert api.get(f"/api/v1/sessions/{sid}/report").status_code == 200

    saved = api.get(f"/api/v1/me/interviews/{sid}", headers=auth(token)).json()
    assert saved["done"] is True and saved["phase"] == "closing"
    assert saved["history"][-1]["text"] == final["closing_message"]
    candidate_turns = [h for h in saved["history"] if h["role"] == "candidate"]
    assert candidate_turns[0]["turn_feedback"]["scores"]["relevance"] == 3
    assert saved["report"]["overall_score"] == 3.0
    assert api.get("/api/v1/me/interviews", headers=auth(token)).json()["interviews"][0]["overall_score"] == 3.0


def test_interviews_are_private(fake, api):  # noqa: F811
    fake()
    owner = register(api)
    other = register(api, username="Mia")
    sid = api.post("/api/v1/sessions", json=SETUP, headers=auth(owner)).json()["session_id"]

    assert api.get("/api/v1/me/interviews", headers=auth(other)).json()["interviews"] == []
    resp = api.get(f"/api/v1/me/interviews/{sid}", headers=auth(other))
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "INTERVIEW_NOT_FOUND"


def test_guest_interview_is_not_saved_and_bad_token_is_refused(fake, api):  # noqa: F811
    fake()
    token = register(api)
    start(api)  # guest
    assert api.get("/api/v1/me/interviews", headers=auth(token)).json()["interviews"] == []
    resp = api.post("/api/v1/sessions", json=SETUP, headers=auth("not-a-token"))
    assert resp.status_code == 401
