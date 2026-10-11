"""Robust parsing of JSON output from the LLM, with retries.

Small models often wrap JSON in prose or code fences, emit <think> blocks,
leave trailing commas, use Python literals or return scores as "4/5".
`parse_json` handles those locally (no extra LLM call). `complete_json`
asks the model to repair its output when it is really unusable; every
retry is a normal, counted LLM call.
"""

import ast
import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError, field_validator

from backend import llm
from backend.interview.prompts import CRITERIA

logger = logging.getLogger("interview")

MAX_JSON_ATTEMPTS = 3

M = TypeVar("M", bound=BaseModel)


class JSONParseError(ValueError):
    pass


def _norm_key(key) -> str:
    return re.sub(r"[\s\-]+", "_", str(key).strip().lower())


class Analysis(BaseModel):
    """Output of the per-answer analysis call."""

    scores: dict[str, int]
    short_tip: str = ""
    follow_up: bool = False

    @field_validator("scores", mode="before")
    @classmethod
    def _normalise_scores(cls, raw):
        if not isinstance(raw, dict):
            raise ValueError("scores must be an object")
        scores = {}
        for key, value in raw.items():
            if _norm_key(key) in CRITERIA:
                scores[_norm_key(key)] = _to_score(value)
        missing = [key for key in CRITERIA if key not in scores]
        if missing:
            raise ValueError(f"missing scores: {', '.join(missing)}")
        return scores

    @field_validator("follow_up", mode="before")
    @classmethod
    def _to_bool(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "ja", "oui", "si", "sì", "1")
        return bool(value)


class CriterionNote(BaseModel):
    comment: str = ""
    evidence: str = ""


class Improvement(BaseModel):
    tip: str
    example_answer: str = ""


class ReportDraft(BaseModel):
    """Output of the final report call (texts only; numbers are computed in code)."""

    criteria: dict[str, CriterionNote] = {}
    strengths: list[str] = []
    improvements: list[Improvement] = []

    @field_validator("criteria", mode="before")
    @classmethod
    def _normalise_criteria(cls, raw):
        if not isinstance(raw, dict):
            return {}
        return {_norm_key(k): v for k, v in raw.items() if _norm_key(k) in CRITERIA and isinstance(v, dict)}

    @field_validator("improvements", mode="before")
    @classmethod
    def _tips_as_objects(cls, raw):
        return [{"tip": item} if isinstance(item, str) else item for item in raw or []]


def _to_score(value) -> int:
    if isinstance(value, dict):  # {"score": 4, "reason": "..."}
        value = value.get("score", value.get("value"))
    match = re.search(r"\d+(\.\d+)?", str(value))
    if not match:
        raise ValueError(f"score is not a number: {value!r}")
    return max(1, min(5, round(float(match.group()))))


def _candidates(text: str):
    """Yield substrings that may contain the JSON object, best guesses first."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    text = text.replace("“", '"').replace("”", '"')
    for fenced in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL):
        yield fenced.strip()
    # Balanced {...} spans, scanning while respecting string literals.
    depth, start, in_str, escape = 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                yield text[start : i + 1]
    if start is not None and depth:  # truncated output: try closing the braces
        yield text[start:] + "}" * depth


def _loads(candidate: str):
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    fixed = re.sub(r",\s*([}\]])", r"\1", candidate)  # trailing commas
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    try:  # Python-style dict: single quotes, True/False/None
        pythonic = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", re.sub(r"\bnull\b", "None", fixed)))
        return ast.literal_eval(pythonic)
    except (ValueError, SyntaxError):
        return None


def parse_json(text: str, model: type[M]) -> M:
    last_error = "no JSON object found"
    for candidate in _candidates(text or ""):
        data = _loads(candidate)
        if not isinstance(data, dict):
            last_error = "invalid JSON syntax"
            continue
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            last_error = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'root'}: {e['msg']}" for e in exc.errors())
    raise JSONParseError(last_error)


def parse_analysis(text: str) -> Analysis:
    return parse_json(text, Analysis)


async def complete_json(messages: list[dict], model: type[M], purpose: str,
                        temperature: float = 0.2, max_tokens: int | None = None) -> tuple[M | None, int, str | None]:
    """Call the LLM until its output parses as `model`, at most MAX_JSON_ATTEMPTS calls.

    Returns (result or None, attempts used, last error).
    """
    error, raw = None, None
    for attempt in range(1, MAX_JSON_ATTEMPTS + 1):
        if error is None:
            prompt = messages
        else:
            prompt = messages + [
                {"role": "assistant", "content": raw or ""},
                {"role": "user", "content": f"Your previous output could not be used: {error}\n"
                                            "Return ONLY the corrected JSON object in the requested shape. No other text."},
            ]
        raw = await llm.chat_completion(
            prompt,
            purpose=purpose if attempt == 1 else f"{purpose}_retry",
            temperature=temperature if attempt == 1 else 0.0,
            **({"max_tokens": max_tokens} if max_tokens else {}),
        )
        try:
            return parse_json(raw, model), attempt, None
        except JSONParseError as exc:
            error = str(exc)
            logger.warning(json.dumps({"event": "json_parse_failed", "purpose": purpose, "attempt": attempt, "error": error}))
    return None, MAX_JSON_ATTEMPTS, error
