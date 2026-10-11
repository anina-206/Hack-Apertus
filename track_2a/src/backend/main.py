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

from fastapi import APIRouter, FastAPI, File, Form, Request, UploadFile
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import config, llm
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

# Inside Aegra (AEGRA_CONFIG is set) Aegra adds CORS itself, from aegra.json "http.cors".
if not os.environ.get("AEGRA_CONFIG"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:8080"],  # Vite dev server, nginx container
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
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
    occupation_id: Optional[str] = None  # one of data/occupations.yaml; optional if posting_id is given
    interviewer_style: str = "friendly"
    mode: Literal["training", "rehearsal"] = "training"
    candidate: Optional[Candidate] = None
    posting_id: Optional[str] = None  # FHGR posting (company); default per occupation and language
    focus: list[str] = Field(default=[], max_length=3)  # criteria to practise (e.g. the report's next_practice)

    @model_validator(mode="after")
    def _known_ids(self):
        if not self.occupation_id and not self.posting_id:
            raise ValueError("occupation_id or posting_id is required")
        if self.occupation_id and self.occupation_id not in config.occupations():
            raise ValueError(f"unknown occupation_id '{self.occupation_id}'")
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
async def create_session(req: SessionRequest) -> dict:
    llm.start_request()
    session_id = str(uuid.uuid4())
    setup = req.model_dump()
    if setup["candidate"]:
        setup["candidate"] = {k: v for k, v in setup["candidate"].items() if v}
    setup["posting_id"] = req.posting_id or config.default_posting_id(req.occupation_id, req.language)
    state = await _llm(engine.start(session_id, setup))
    question = state["current_question"]
    posting = config.postings().get(setup["posting_id"] or "")
    return {
        "session_id": session_id,
        "phase": position(state).phase,
        "progress": progress(position(state)),
        "question": {"id": question["id"], "text": question["text"]},
        "company": {"name": posting["company"]["name"], "place": posting["company"]["place"]} if posting else None,
        "interviewer": {"name": posting["interviewer"]["name"], "role": posting["interviewer"]["role"],
                        "voice": config.interviewer_voice(posting["id"])} if posting else None,
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
    logger.info(json.dumps({"event": "report", "session_id": session_id, "llm_calls": llm.calls_in_request()}))
    return report


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
async def transcribe(audio: UploadFile = File(...), language: VoiceLanguage = Form(...)) -> dict:
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise ApiError(400, "INVALID_REQUEST", "audio: empty file")
    if len(data) > MAX_AUDIO_BYTES:
        raise ApiError(400, "INVALID_REQUEST", "audio: larger than 5 MB")
    try:
        return await asyncio.to_thread(stt.transcribe, data, language)
    except ValueError as exc:
        raise ApiError(400, "INVALID_REQUEST", f"audio: {exc}")
    except VoiceUnavailable as exc:
        raise ApiError(503, "VOICE_UNAVAILABLE", str(exc))


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
