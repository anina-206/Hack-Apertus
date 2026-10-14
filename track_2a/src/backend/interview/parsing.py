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
from typing import Optional, TypeVar

from pydantic import BaseModel, ValidationError, field_validator

from backend import llm
from backend.interview import rubric, safety
from backend.interview.prompts import CRITERIA

logger = logging.getLogger("interview")

MAX_JSON_ATTEMPTS = 3

M = TypeVar("M", bound=BaseModel)


class JSONParseError(ValueError):
    pass


def _norm_key(key) -> str:
    return re.sub(r"[\s\-]+", "_", str(key).strip().lower())


# Keys the model may use for a criterion: the id or its label in any language ("Klarheit", "Pertinence").
_CRITERION_ALIASES = {_norm_key(key): key for key in CRITERIA}
_CRITERION_ALIASES.update({_norm_key(label): key for label, key in rubric.all_labels().items()})
_CRITERION_ALIASES.update({"examples": "concrete_examples", "self_awareness": "self_reflection",
                           "demeanour": "demeanor"})


class Analysis(BaseModel):
    """Output of the per-answer analysis call. Scores are 1-4, or None if the answer shows nothing about it."""

    scores: dict[str, Optional[int]]
    short_tip: str = ""
    follow_up: bool = False
    problem_flags: list[str] = []

    @field_validator("problem_flags", mode="before")
    @classmethod
    def _known_flags(cls, raw):
        items = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
        return [f for f in dict.fromkeys(_norm_key(i) for i in items) if f in safety.PROBLEM_FLAGS]

    @field_validator("scores", mode="before")
    @classmethod
    def _normalise_scores(cls, raw):
        if not isinstance(raw, dict):
            raise ValueError("scores must be an object")
        scores = {key: None for key in CRITERIA}  # criteria the model leaves out count as not observed
        for key, value in raw.items():
            criterion = _CRITERION_ALIASES.get(_norm_key(key))
            if criterion:
                scores[criterion] = _to_score(value)
        if all(value is None for value in scores.values()):
            raise ValueError("no criterion scored")
        return scores

    @field_validator("follow_up", mode="before")
    @classmethod
    def _to_bool(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "ja", "oui", "si", "sì", "1")
        return bool(value)



# Names the model may use instead of "comment".
_COMMENT_KEYS = ("comment", "text", "reason", "explanation", "feedback")


def _list_key(item: dict) -> str:
    return str(next((item[k] for k in ("id", "criterion", "key", "name", "label") if item.get(k)), ""))


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
    closing: str = ""

    @field_validator("closing", mode="before")
    @classmethod
    def _text_only(cls, raw):
        return raw if isinstance(raw, str) else ""

    @field_validator("criteria", mode="before")
    @classmethod
    def _normalise_criteria(cls, raw):
        # Accept {"relevance": {...}}, {"Relevanz": "text"} and [{"id": "relevance", "comment": ...}].
        if isinstance(raw, list):
            raw = {_list_key(item): item for item in raw if isinstance(item, dict)}
        if not isinstance(raw, dict):
            return {}
        notes = {}
        for key, value in raw.items():
            criterion = _CRITERION_ALIASES.get(_norm_key(key))
            if criterion is None:
                continue
            if isinstance(value, str):
                value = {"comment": value}
            if isinstance(value, dict):
                comment = next((value[k] for k in _COMMENT_KEYS if isinstance(value.get(k), str)), "")
                evidence = value.get("evidence") if isinstance(value.get("evidence"), str) else ""
                notes[criterion] = {"comment": comment, "evidence": evidence}
        return notes

    @field_validator("improvements", mode="before")
    @classmethod
    def _tips_as_objects(cls, raw):
        return [{"tip": item} if isinstance(item, str) else item for item in raw or []]


_NOT_OBSERVED = re.compile(r"^\s*(null|none|n/?a|-+|keine?|not observed|nicht beobachtet)?\s*$", re.IGNORECASE)


def _to_score(value) -> Optional[int]:
    if isinstance(value, dict):  # {"score": 4, "reason": "..."}
        value = value.get("score", value.get("value"))
    if value is None or _NOT_OBSERVED.match(str(value)):
        return None
    match = re.search(r"\d+(\.\d+)?", str(value))
    if not match:
        raise ValueError(f"score is not a number: {value!r}")
    return rubric.clamp(float(match.group()))


def _candidates(text: str):
    """Yield substrings that may contain the JSON object, best guesses first."""
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


def _escape_inner_quotes(text: str) -> str:
    """Escape '"' inside strings that does not end the string (`"evidence": "Ich sagte "Lego""`).

    A quote ends a string only if the next non-space character is , : } ] or the end of the text.
    """
    out, in_str, escape = [], False, False
    for i, ch in enumerate(text):
        if in_str and escape:
            escape = False
        elif in_str and ch == "\\":
            escape = True
        elif ch == '"':
            if not in_str:
                in_str = True
            else:
                rest = text[i + 1:].lstrip()
                if rest and rest[0] not in ",:}]":
                    out.append('\\"')
                    continue
                in_str = False
        out.append(ch)
    return "".join(out)


# The last error of _loads, with the text around it, for the log (see complete_json)
_last_syntax_error = ""


def _loads(candidate: str):
    global _last_syntax_error
    fixed = re.sub(r",\s*([}\]])", r"\1", candidate)  # trailing commas
    # strict=False: line breaks inside strings, which the model often writes in longer texts
    for text in (candidate, fixed, _escape_inner_quotes(fixed)):
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError as exc:
            if text is candidate:
                _last_syntax_error = f"{exc.msg} at {exc.pos}/{len(text)}: ...{text[max(0, exc.pos - 60):exc.pos + 20]!r}"
    try:  # Python-style dict: single quotes, True/False/None
        pythonic = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", re.sub(r"\bnull\b", "None", fixed)))
        return ast.literal_eval(pythonic)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return None


def parse_json(text: str, model: type[M]) -> M:
    last_error = "no JSON object found"
    text = text or ""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    # Curly quotes are usually German quotation marks inside a string („Lego“), which are valid JSON.
    # Only if that fails, read them as JSON quotes (some outputs use “key”: “value”).
    variants = [text] + ([text.replace("“", '"').replace("”", '"')] if "“" in text or "”" in text else [])
    for candidate in (c for variant in variants for c in _candidates(variant)):
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
            logger.warning(json.dumps({"event": "json_parse_failed", "purpose": purpose, "attempt": attempt, "error": error,
                                       "detail": _last_syntax_error, "length": len(raw or "")}, ensure_ascii=False))
    return None, MAX_JSON_ATTEMPTS, error
