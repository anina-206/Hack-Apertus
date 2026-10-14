"""HTTP API. The contract is docs/api.md: change it there first, then here.

Runs standalone (uvicorn backend.main:app) or as the custom app inside Aegra (aegra.json "http"),
which then adds the Agent Protocol routes (/threads, /runs, ...) for the graph `agent` (agent.py).
"""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import config, llm
from backend.accounts import AccountError, Limits, Store
from backend.interview import application, dialect
from backend.interview import company as company_generator
from backend.interview.graph import InterviewEngine, position
from backend.interview.phases import progress
from backend.interview.prompts import CRITERIA
from backend.interview.report import ReportUnavailable, build_report
from backend.voice import VoiceUnavailable, flag, stt, tts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("api")

engine = InterviewEngine()  # in memory; replaced by a SQLite-backed engine at startup if SESSIONS_DB is set


def _preload_voice() -> None:
    """Load Whisper and Piper in the background (VOICE_PRELOAD=false skips it, e.g. in tests)."""
    if not flag("VOICE_PRELOAD", True):
        return
    if stt.enabled():
        asyncio.get_running_loop().run_in_executor(None, stt.preload)
    asyncio.get_running_loop().run_in_executor(None, tts.preload)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """With SESSIONS_DB=/path/sessions.db, sessions survive a backend restart (LangGraph SQLite checkpointer)."""
    global engine
    _preload_voice()
    db = os.environ.get("SESSIONS_DB", "").strip()
    if not db:
        yield
        return
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    Path(db).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        engine = InterviewEngine(saver)
        logger.info(json.dumps({"event": "sessions_db", "path": db}))
        yield


app = FastAPI(title="Schnupper Interview Coach", lifespan=lifespan)
api = APIRouter(prefix="/api/v1")
store = Store()  # SQLite file (DB_PATH, default storage/app.db)
limits = Limits()  # rate limits for login and registration

# Inside Aegra (AEGRA_CONFIG is set) Aegra adds CORS itself, from aegra.json "http.cors".
if not os.environ.get("AEGRA_CONFIG"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:8080"],  # Vite dev server, nginx container
        allow_methods=["GET", "POST", "DELETE"],
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


def _ours(request: Request) -> bool:
    """Our error format only for our API; Aegra's routes keep FastAPI's default format."""
    return request.url.path.startswith("/api/v1")


@app.exception_handler(AccountError)
async def _account_error(_: Request, exc: AccountError):
    response = _error(exc.status, exc.code, exc.message)
    if exc.retry_after:
        response.headers["Retry-After"] = str(exc.retry_after)
    return response


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    if not _ours(request):
        return await request_validation_exception_handler(request, exc)
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return _error(400, "INVALID_REQUEST", f"{field}: {first.get('msg', 'invalid request')}".strip(": "))


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    if not _ours(request):
        return await http_exception_handler(request, exc)
    # Unknown routes, wrong methods etc. (FastAPI would answer {"detail": ...}).
    return _error(exc.status_code, "INVALID_REQUEST", str(exc.detail))


@app.exception_handler(Exception)
async def _unexpected_error(request: Request, exc: Exception):
    logger.exception("Unexpected error")
    if not _ours(request):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
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
    occupation_id: Optional[str] = None  # one of data/occupations.yaml; optional if posting_id or occupation_name is given
    occupation_name: Optional[str] = Field(default=None, max_length=100)  # any other apprenticeship, free text
    interviewer_style: str = "friendly"
    mode: Literal["training", "rehearsal"] = "training"
    dialect: Optional[str] = None  # only for language "gsw": zh, be, bs, gr or vs (default zh)
    candidate: Optional[Candidate] = None
    application_text: Optional[str] = Field(default=None, max_length=application.MAX_TEXT_CHARS)  # from /application/extract
    posting_id: Optional[str] = None  # FHGR posting (company); default per occupation and language
    focus: list[str] = Field(default=[], max_length=3)  # criteria to practise (e.g. the report's next_practice)

    @model_validator(mode="after")
    def _known_ids(self):
        if not (self.occupation_id or self.posting_id or (self.occupation_name or "").strip()):
            raise ValueError("occupation_id, posting_id or occupation_name is required")
        if self.occupation_id and self.occupation_id not in config.occupations():
            raise ValueError(f"unknown occupation_id '{self.occupation_id}'")
        if self.dialect and self.dialect not in dialect.DIALECTS:
            raise ValueError(f"unknown dialect '{self.dialect}'")
        if self.interviewer_style not in config.interviewer_styles():
            raise ValueError(f"unknown interviewer_style '{self.interviewer_style}'")
        if self.posting_id and self.posting_id not in config.postings():
            raise ValueError(f"unknown posting_id '{self.posting_id}'")
        unknown = [c for c in self.focus if c not in CRITERIA]
        if unknown:
            raise ValueError(f"unknown focus criteria: {', '.join(unknown)}")
        return self


class AnswerRequest(BaseModel):
    question_id: str
    text: str = Field(min_length=1, max_length=4000)


class Credentials(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class PasswordConfirm(BaseModel):
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


@api.post("/application/extract")
async def extract_application(file: UploadFile) -> dict:
    """Plain text of an uploaded application (PDF, .docx or text). Nothing is stored."""
    data = await file.read(application.MAX_UPLOAD_BYTES + 1)
    if len(data) > application.MAX_UPLOAD_BYTES:
        raise ApiError(400, "INVALID_REQUEST", "The file is too large (max. 5 MB).")
    try:
        text = await asyncio.to_thread(application.extract_text, file.filename or "", data)
    except ValueError as exc:
        raise ApiError(400, "INVALID_REQUEST", str(exc))
    return {"filename": file.filename, "text": text[:application.MAX_TEXT_CHARS], "chars": min(len(text), application.MAX_TEXT_CHARS),
            "truncated": len(text) > application.MAX_TEXT_CHARS}


@api.post("/sessions", status_code=201)
async def create_session(req: SessionRequest, request: Request) -> dict:
    user = _require_user(request) if _bearer(request) else None  # a bad token is an error, not a silent guest
    llm.start_request()
    session_id = str(uuid.uuid4())
    setup = req.model_dump()
    setup.pop("application_text")  # the text itself is never kept, only its summary
    setup["dialect"] = (req.dialect or dialect.DEFAULT_DIALECT) if req.language == "gsw" else None
    if setup["candidate"]:
        setup["candidate"] = {k: v for k, v in setup["candidate"].items() if v}
    name = (req.occupation_name or "").strip() or None
    if name and not req.occupation_id and not req.posting_id:
        # An apprenticeship outside data/occupations.yaml: generic entry, no company
        setup["occupation_id"], setup["occupation_name"] = config.GENERIC_OCCUPATION, name
    else:
        setup["occupation_name"] = None  # only used when no known occupation or posting is given
    # The application letter names the company and the contact person: the interviewer speaks as them
    application_summary, application_asks, company = None, [], {}
    if (req.application_text or "").strip():
        try:
            application_summary, application_asks, company = await application.summarize(
                req.application_text, req.language)
            application_summary = application_summary or None
        except Exception:
            logger.exception("Application summary failed")  # the interview works without it
    setup["company"] = company or None
    # Without a company in the letter an FHGR posting of the occupation is used (an explicit posting_id wins):
    # the default one of a known occupation, else one found by the apprenticeship's name
    if req.posting_id or company:
        setup["posting_id"] = req.posting_id
    elif setup["occupation_name"]:
        setup["posting_id"] = config.posting_for_name(setup["occupation_name"], req.language)
    else:
        setup["posting_id"] = config.default_posting_id(setup["occupation_id"], req.language)
    setup["application_summary"] = application_summary
    setup["application_asks"] = application_asks  # points the interviewer asks about, one per question
    # No contact person from a posting or the letter: a random interviewer, so it is not always the same one
    setup["persona"] = (None if config.interviewer_of(config.posting_for(setup))
                        else config.random_interviewer(req.language))
    if not setup["posting_id"] and not setup["company"]:
        # No FHGR posting for this apprenticeship and no letter: Apertus invents a company (one call), with the
        # random interviewer as the contact person. Without it the interview simply has no company.
        try:
            setup["company"] = await company_generator.generate(
                config.occupation_for(setup["occupation_id"], None, setup["occupation_name"]), req.language,
                company_generator.town(req.language, setup["dialect"]),
                setup["persona"]["name"], setup["persona"]["role"]) or None
        except Exception:
            logger.exception("Company generation failed")
    state = await _llm(engine.start(session_id, setup))
    question = state["current_question"]
    posting = config.posting_for(state)
    if user:
        store.save_interview(session_id, user["id"], state)
    return {
        "session_id": session_id,
        "phase": position(state).phase,
        "progress": progress(position(state)),
        "question": {"id": question["id"], "text": question["text"]},
        "company": config.company_of(posting),
        "interviewer": config.interviewer_of(posting, state.get("persona")),
        "application_summary": application_summary,
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
        turn_feedback = {"short_tip": analysis["short_tip"], "scores": analysis["scores"],
                         "problem_flags": analysis.get("problem_flags", [])}

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
        "occupation_name": state.get("occupation_name"),
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

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_password_attempt(ip: str, username: str, action):
    """Runs `action` (a password check) under the login limits and returns its result. Only failed attempts count."""
    key = f"{ip}|{username.strip().lower()}"
    limits.login_user.check(key)
    limits.login_ip.check(ip)
    try:
        result = action()
    except AccountError as exc:
        if exc.code == "INVALID_CREDENTIALS":
            limits.login_user.count(key)
            limits.login_ip.count(ip)
        raise
    limits.login_user.reset(key)
    return result


@api.post("/auth/register", status_code=201)
async def register(req: Credentials, request: Request) -> dict:
    ip = _client_ip(request)
    limits.register.check(ip)
    limits.register.count(ip)
    token, user = store.register(req.username, req.password)
    return {"token": token, "user": user}


@api.post("/auth/login")
async def login(req: Credentials, request: Request) -> dict:
    token, user = _check_password_attempt(_client_ip(request), req.username,
                                          lambda: store.login(req.username, req.password))
    return {"token": token, "user": user}


@api.post("/auth/logout", status_code=204)
async def logout(request: Request) -> Response:
    _require_user(request)
    store.logout(_bearer(request))
    return Response(status_code=204)


@api.get("/auth/me")
async def me(request: Request) -> dict:
    return _require_user(request)


@api.delete("/auth/me", status_code=204)
async def delete_account(req: PasswordConfirm, request: Request) -> Response:
    user = _require_user(request)
    _check_password_attempt(_client_ip(request), user["username"], lambda: store.delete_account(user["id"], req.password))
    return Response(status_code=204)


@api.get("/me/interviews")
async def my_interviews(request: Request) -> dict:
    return {"interviews": store.list_interviews(_require_user(request)["id"])}


@api.delete("/me/interviews/{session_id}", status_code=204)
async def delete_my_interview(session_id: str, request: Request) -> Response:
    if not store.delete_interview(_require_user(request)["id"], session_id):
        raise ApiError(404, "INTERVIEW_NOT_FOUND", "No saved interview with this id.")
    await engine.delete(session_id)
    return Response(status_code=204)


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


# --- Voice (docs/api.md: POST /transcribe, POST /speech) -----------------------------------------

MAX_AUDIO_BYTES = 5 * 1024 * 1024
VoiceLanguage = Literal["de", "fr", "it", "gsw"]


@api.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: VoiceLanguage = Form(...),
                     session_id: Optional[str] = Form(None)) -> dict:
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise ApiError(400, "INVALID_REQUEST", "audio: empty file")
    if len(data) > MAX_AUDIO_BYTES:
        raise ApiError(400, "INVALID_REQUEST", "audio: larger than 5 MB")
    try:
        return await asyncio.to_thread(stt.transcribe, data, language, await _vocabulary_hint(session_id, language))
    except ValueError as exc:
        raise ApiError(400, "INVALID_REQUEST", f"audio: {exc}")
    except VoiceUnavailable as exc:
        raise ApiError(503, "VOICE_UNAVAILABLE", str(exc))


async def _vocabulary_hint(session_id: Optional[str], language: str) -> str:
    """Occupation and company of the session for Whisper; empty without (or with an unknown) session."""
    state = await engine.get_state(session_id) if session_id else None
    if not state:
        return ""
    occupation = config.occupation_for(state.get("occupation_id"), state.get("posting_id"), state.get("occupation_name"))
    label = occupation["label"].get("de" if language == "gsw" else language) or occupation["label"]["de"]
    company = config.company_of(config.posting_for(state))
    return stt.vocabulary_hint(language, label, company["name"] if company else "")


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=tts.MAX_CHARS)
    language: VoiceLanguage
    voice: Literal["female", "male"] = "female"


@api.post("/speech")
async def speech(req: SpeechRequest) -> Response:
    try:
        audio, media_type, engine_name = await asyncio.to_thread(tts.speech, req.text.strip(), req.language, req.voice)
    except VoiceUnavailable as exc:
        raise ApiError(503, "VOICE_UNAVAILABLE", str(exc))
    return Response(audio, media_type=media_type, headers={"X-TTS-Engine": engine_name})


app.include_router(api)
