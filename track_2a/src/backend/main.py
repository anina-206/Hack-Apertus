"""HTTP API. The contract is docs/api.md: change it there first, then here."""

import json
import logging
import os
import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import config, llm
from backend.accounts import AccountError, Store
from backend.interview.graph import InterviewEngine, position
from backend.interview.phases import progress
from backend.interview.report import ReportUnavailable, build_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("api")

app = FastAPI(title="Schnupper Interview Coach")
api = APIRouter(prefix="/api/v1")
engine = InterviewEngine()
store = Store()  # SQLite file (DB_PATH, default storage/app.db)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],  # Vite dev server, nginx container
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# --- Errors (docs/api.md section 1) ---------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(AccountError)
async def _account_error(_: Request, exc: AccountError):
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return _error(400, "INVALID_REQUEST", f"{field}: {first.get('msg', 'invalid request')}".strip(": "))


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, exc: StarletteHTTPException):
    # Unknown routes, wrong methods etc. (FastAPI would answer {"detail": ...}).
    return _error(exc.status_code, "INVALID_REQUEST", str(exc.detail))


@app.exception_handler(Exception)
async def _unexpected_error(_: Request, exc: Exception):
    logger.exception("Unexpected error")
    return _error(500, "INTERNAL_ERROR", "Unexpected error in the backend.")


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.startswith("Bearer ") else None


def _require_user(request: Request) -> dict:
    token = _bearer(request)
    user = store.user_for_token(token) if token else None
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Missing, invalid or expired token.")
    return user


def _save(session_id: str, state: dict, turn_feedback: Optional[dict] = None, question_id: Optional[str] = None):
    """Saves the conversation if the session belongs to a user. A failing save must not break the interview."""
    user_id = store.owner(session_id)
    if user_id:
        try:
            store.save_interview(session_id, user_id, state, turn_feedback, question_id)
        except Exception:
            logger.exception("Could not save interview %s", session_id)


async def _llm(coro):
    try:
        return await coro
    except (ApiError, ReportUnavailable):
        raise
    except Exception as exc:
        logger.exception("LLM call failed")
        raise ApiError(502, "LLM_UNAVAILABLE", f"Apertus did not answer: {type(exc).__name__}: {exc}")


async def _session(session_id: str) -> dict:
    state = await engine.get_state(session_id)
    if state is None:
        raise ApiError(404, "SESSION_NOT_FOUND", "No session with this id.")
    return state


# --- Models --------------------------------------------------------------------------------------

class Candidate(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=50)
    school_level: Optional[str] = Field(default=None, max_length=50)
    interests: Optional[str] = Field(default=None, max_length=300)


class SessionRequest(BaseModel):
    language: Literal["de", "fr", "it", "gsw"]
    occupation_id: str
    interviewer_style: str = "friendly"
    mode: Literal["training", "rehearsal"] = "training"
    candidate: Optional[Candidate] = None

    @model_validator(mode="after")
    def _known_ids(self):
        if self.occupation_id not in config.occupations():
            raise ValueError(f"unknown occupation_id '{self.occupation_id}'")
        if self.interviewer_style not in config.interviewer_styles():
            raise ValueError(f"unknown interviewer_style '{self.interviewer_style}'")
        return self


class AnswerRequest(BaseModel):
    question_id: str
    text: str = Field(min_length=1, max_length=4000)


class Credentials(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class ChatRequest(BaseModel):
    message: str = "Hallo! Stell dich bitte kurz vor."


# --- Endpoints -----------------------------------------------------------------------------------

@api.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": os.environ.get("LLM_NAME") or None}


@api.get("/config")
async def get_config() -> dict:
    return config.public_config()


@api.post("/sessions", status_code=201)
async def create_session(req: SessionRequest, request: Request) -> dict:
    user = _require_user(request) if _bearer(request) else None  # a bad token is an error, not a silent guest
    llm.start_request()
    session_id = str(uuid.uuid4())
    setup = req.model_dump()
    if setup["candidate"]:
        setup["candidate"] = {k: v for k, v in setup["candidate"].items() if v}
    state = await _llm(engine.start(session_id, setup))
    question = state["current_question"]
    if user:
        store.save_interview(session_id, user["id"], state)
    return {
        "session_id": session_id,
        "phase": position(state).phase,
        "progress": progress(position(state)),
        "question": {"id": question["id"], "text": question["text"]},
    }


@api.post("/sessions/{session_id}/answers")
async def answer(session_id: str, req: AnswerRequest) -> dict:
    started = time.perf_counter()
    current = await _session(session_id)
    if current.get("done"):
        raise ApiError(409, "INTERVIEW_FINISHED", "The interview is already finished.")
    if req.question_id != current["current_question"]["id"]:
        raise ApiError(409, "WRONG_QUESTION", f"Current question is {current['current_question']['id']}.")

    request_id = llm.start_request()
    state = await _llm(engine.answer(session_id, req.text))
    calls = llm.calls_in_request()
    meta = {"llm_calls": calls, "latency_ms": round((time.perf_counter() - started) * 1000)}
    logger.info(json.dumps({"event": "answer", "request_id": request_id, "session_id": session_id,
                            "calls_per_answer": calls, "analysis_attempts": state.get("analysis_attempts")}))

    analysis = state.get("analysis")
    turn_feedback = None
    if state["mode"] == "training" and analysis:
        turn_feedback = {"short_tip": analysis["short_tip"], "scores": analysis["scores"]}

    _save(session_id, state, turn_feedback, req.question_id)

    pos = position(state)
    if state.get("done"):
        return {"done": True, "phase": pos.phase, "progress": progress(pos), "question": None,
                "closing_message": state["closing_message"], "turn_feedback": turn_feedback, "meta": meta}
    return {"done": False, "phase": pos.phase, "progress": progress(pos), "question": state["current_question"],
            "turn_feedback": turn_feedback, "meta": meta}


@api.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    state = await _session(session_id)
    pos = position(state)
    return {
        "session_id": session_id,
        "language": state["language"],
        "occupation_id": state["occupation_id"],
        "mode": state["mode"],
        "done": state.get("done", False),
        "phase": pos.phase,
        "progress": progress(pos),
        "history": state.get("transcript", []),
        "current_question_id": (state.get("current_question") or {}).get("id"),
    }


@api.get("/sessions/{session_id}/report")
async def get_report(session_id: str) -> dict:
    state = await _session(session_id)
    if not state.get("done"):
        raise ApiError(409, "INTERVIEW_NOT_FINISHED", "The interview is not finished yet.")
    if state.get("report"):
        return state["report"]

    llm.start_request()
    try:
        report = await _llm(build_report(session_id, state))
    except ReportUnavailable as exc:
        raise ApiError(502, "LLM_UNAVAILABLE", str(exc))
    await engine.save_report(session_id, report)
    _save(session_id, {**state, "report": report})
    logger.info(json.dumps({"event": "report", "session_id": session_id, "llm_calls": llm.calls_in_request()}))
    return report


# --- Accounts (docs/api.md section 3b) ---------------------------------------------------------

@api.post("/auth/register", status_code=201)
async def register(req: Credentials) -> dict:
    token, user = store.register(req.username, req.password)
    return {"token": token, "user": user}


@api.post("/auth/login")
async def login(req: Credentials) -> dict:
    token, user = store.login(req.username, req.password)
    return {"token": token, "user": user}


@api.post("/auth/logout", status_code=204)
async def logout(request: Request) -> Response:
    _require_user(request)
    store.logout(_bearer(request))
    return Response(status_code=204)


@api.get("/auth/me")
async def me(request: Request) -> dict:
    return _require_user(request)


@api.get("/me/interviews")
async def my_interviews(request: Request) -> dict:
    return {"interviews": store.list_interviews(_require_user(request)["id"])}


@api.get("/me/interviews/{session_id}")
async def my_interview(session_id: str, request: Request) -> dict:
    interview = store.get_interview(_require_user(request)["id"], session_id)
    if interview is None:
        raise ApiError(404, "INTERVIEW_NOT_FOUND", "No saved interview with this id.")
    return interview


@api.post("/chat")
async def chat(req: ChatRequest) -> dict:
    """Dev only: one raw call to Apertus to check the connection."""
    request_id = llm.start_request()
    text = await _llm(llm.chat_completion([{"role": "user", "content": req.message}], purpose="chat_test"))
    return {"answer": text, "request_id": request_id, "llm_calls": llm.calls_in_request()}


app.include_router(api)
