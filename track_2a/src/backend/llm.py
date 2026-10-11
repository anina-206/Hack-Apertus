"""Apertus client (OpenAI-compatible) with per-request call counting.

Every LLM call goes through `chat_completion`, which logs one JSON line
(`event=llm_call`) and increments the counter of the current request.
The counter lets us report `calls_per_answer` (gate: average < 5).
"""

import contextvars
import json
import logging
import os
import re
import time
import uuid
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger("llm")

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
_request_calls: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar("request_calls", default=None)

_total_calls = 0
_client: Optional[AsyncOpenAI] = None


class LLMConfigError(RuntimeError):
    pass


def _config() -> tuple[str, str, str]:
    names = ("LLM_NAME", "LLM_BASE_URL", "LLM_API_KEY")
    values = [os.environ.get(n, "").strip() for n in names]
    missing = [n for n, v in zip(names, values) if not v]
    if missing:
        raise LLMConfigError(f"Missing environment variables: {', '.join(missing)}")
    return values[0], values[1], values[2]


def _get_client() -> tuple[AsyncOpenAI, str]:
    global _client
    model, base_url, api_key = _config()
    if _client is None:
        _client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _client, model


# UTF-8 bytes read as Latin-1, e.g. "Ã¤" instead of "ä". The model sometimes emits these itself.
_MOJIBAKE = re.compile(r"[\u00c2-\u00f4][\u0080-\u00bf]+")


def fix_mojibake(text: str) -> str:
    def repair(match: re.Match) -> str:
        try:
            return match.group().encode("latin-1").decode("utf-8")
        except UnicodeDecodeError:
            return match.group()
    return _MOJIBAKE.sub(repair, text)


def start_request() -> str:
    """Begin counting LLM calls for one user-facing answer."""
    request_id = uuid.uuid4().hex[:12]
    _request_id.set(request_id)
    _request_calls.set([0])
    return request_id


def calls_in_request() -> int:
    counter = _request_calls.get()
    return counter[0] if counter else 0


def total_calls() -> int:
    return _total_calls


async def chat_completion(messages: list[dict], purpose: str = "chat", **kwargs) -> str:
    """Single entry point for all LLM calls. `purpose` labels the call in the log."""
    global _total_calls
    client, model = _get_client()

    counter = _request_calls.get()
    if counter is not None:
        counter[0] += 1
    _total_calls += 1

    started = time.perf_counter()
    status = "ok"
    usage = None
    try:
        response = await client.chat.completions.create(model=model, messages=messages, **kwargs)
        usage = response.usage
        return fix_mojibake(response.choices[0].message.content or "")
    except Exception as exc:
        status = f"error: {type(exc).__name__}"
        raise
    finally:
        logger.info(json.dumps({
            "event": "llm_call",
            "request_id": _request_id.get(),
            "purpose": purpose,
            "call_index": counter[0] if counter is not None else None,
            "total_calls": _total_calls,
            "model": model,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "status": status,
        }))
