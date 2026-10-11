"""Accounts and saved interviews (docs/api.md section 3b), against a fake LLM and a temporary database."""

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.accounts import AccountError, Limits, RateLimiter, Store
from backend.interview.graph import InterviewEngine
from backend.tests.test_graph import SETUP, fake, run_until, send, start  # noqa: F401  (fake is a fixture)

CREDS = {"username": "Lara", "password": "geheim1234"}


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "engine", InterviewEngine())
    monkeypatch.setattr(main, "store", Store(str(tmp_path / "test.db")))
    monkeypatch.setattr(main, "limits", Limits())  # fresh counters for every test
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
    assert saved["company"]["name"] and saved["interviewer"]["name"]  # from the default posting
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


# --- Rate limiting and deleting the account (docs/api.md section 3b) --------------------------------

def login(api, password, username="Lara"):
    return api.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_is_locked_after_five_wrong_passwords(api):
    register(api)
    for _ in range(5):
        assert login(api, "falsch12345").status_code == 401
    locked = login(api, CREDS["password"])  # even the right password is refused now
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert int(locked.headers["Retry-After"]) > 0


def test_lock_is_per_username_and_a_good_login_resets_the_counter(api):
    register(api)
    register(api, username="Mia")
    for _ in range(4):
        login(api, "falsch12345")
    assert login(api, CREDS["password"]).status_code == 200  # resets the counter of this username
    for _ in range(4):
        login(api, "falsch12345")
    assert login(api, CREDS["password"]).status_code == 200  # still not locked
    for _ in range(5):
        login(api, "falsch12345", username="Mia")
    assert login(api, "geheim1234", username="Mia").status_code == 429
    assert login(api, CREDS["password"]).status_code == 200  # Lara is not affected by Mia's lock


def test_registration_is_limited_per_ip(api):
    for i in range(10):
        register(api, username=f"user{i:02d}")
    resp = api.post("/api/v1/auth/register", json={"username": "user99", "password": "geheim1234"})
    assert resp.status_code == 429


def test_rate_limiter_forgets_after_the_window():
    now = [0.0]
    limiter = RateLimiter(2, 60, clock=lambda: now[0])
    limiter.count("k")
    limiter.count("k")
    with pytest.raises(AccountError) as err:
        limiter.check("k")
    assert err.value.status == 429 and err.value.retry_after == 61
    now[0] = 61.0
    limiter.check("k")  # window is over


def test_delete_account_removes_everything(fake, api):  # noqa: F811
    fake()
    token = register(api)
    sid = api.post("/api/v1/sessions", json=SETUP, headers=auth(token)).json()["session_id"]

    wrong = api.request("DELETE", "/api/v1/auth/me", json={"password": "falsch12345"}, headers=auth(token))
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert api.get("/api/v1/auth/me", headers=auth(token)).status_code == 200  # nothing was deleted

    done = api.request("DELETE", "/api/v1/auth/me", json={"password": CREDS["password"]}, headers=auth(token))
    assert done.status_code == 204
    assert api.get("/api/v1/auth/me", headers=auth(token)).status_code == 401  # token is gone
    assert login(api, CREDS["password"]).json()["error"]["code"] == "INVALID_CREDENTIALS"  # user is gone
    with main.store._db() as db:
        assert db.execute("SELECT COUNT(*) FROM interviews WHERE session_id = ?", (sid,)).fetchone()[0] == 0
    # The username is free again
    assert api.post("/api/v1/auth/register", json=CREDS).status_code == 201


def test_delete_account_needs_a_token(api):
    resp = api.request("DELETE", "/api/v1/auth/me", json={"password": "geheim1234"})
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_company_from_the_letter_is_saved_with_the_interview(fake, api):  # noqa: F811
    fake()
    token = register(api)
    sid = api.post("/api/v1/sessions", json={**SETUP, "application_text": "Sehr geehrte Frau Keller ..."},
                   headers=auth(token)).json()["session_id"]
    saved = api.get(f"/api/v1/me/interviews/{sid}", headers=auth(token)).json()
    assert saved["company"] == {"name": "Muster Garage AG", "place": "Chur"}
    assert saved["interviewer"] == {"name": "Frau Keller", "role": "Berufsbildnerin", "voice": "female"}


# --- Deleting one saved interview (docs/api.md section 3b) -------------------------------------------------------

def test_a_saved_interview_can_be_deleted(fake, api):  # noqa: F811
    fake()
    token = register(api)
    keep = api.post("/api/v1/sessions", json=SETUP, headers=auth(token)).json()["session_id"]
    drop = api.post("/api/v1/sessions", json=SETUP, headers=auth(token)).json()["session_id"]

    resp = api.delete(f"/api/v1/me/interviews/{drop}", headers=auth(token))
    assert resp.status_code == 204 and resp.content == b""

    listed = [i["session_id"] for i in api.get("/api/v1/me/interviews", headers=auth(token)).json()["interviews"]]
    assert listed == [keep]
    assert api.get(f"/api/v1/me/interviews/{drop}", headers=auth(token)).status_code == 404
    # the running session is gone too, the other one is untouched
    assert api.get(f"/api/v1/sessions/{drop}").status_code == 404
    assert api.get(f"/api/v1/sessions/{keep}").status_code == 200
    # a second delete finds nothing
    again = api.delete(f"/api/v1/me/interviews/{drop}", headers=auth(token))
    assert again.status_code == 404 and again.json()["error"]["code"] == "INTERVIEW_NOT_FOUND"


def test_nobody_can_delete_someone_elses_interview(fake, api):  # noqa: F811
    fake()
    owner = register(api)
    other = register(api, username="Mia")
    sid = api.post("/api/v1/sessions", json=SETUP, headers=auth(owner)).json()["session_id"]

    assert api.delete(f"/api/v1/me/interviews/{sid}", headers=auth(other)).status_code == 404
    assert api.get(f"/api/v1/me/interviews/{sid}", headers=auth(owner)).status_code == 200  # still there
    assert api.get(f"/api/v1/sessions/{sid}").status_code == 200


def test_deleting_an_interview_needs_a_token(api):
    resp = api.delete("/api/v1/me/interviews/some-id")
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "UNAUTHORIZED"
