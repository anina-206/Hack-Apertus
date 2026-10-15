"""FHGR rubric: 11 criteria, each scored 1-4 or null (= nothing observed in the interview).

Loaded from datasets/rubric/criteria.json (copied from the FHGR repo), so the
criteria, labels and level descriptions are exactly the ones of the challenge.
"""

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Optional

RUBRIC_FILE = Path(__file__).resolve().parents[3] / "datasets" / "rubric" / "criteria.json"

SCALE_MIN, SCALE_MAX = 1, 4

# Shown instead of a score when a criterion was not observed (criteria.json only has de/en).
NOT_OBSERVED = {
    "de": "Dazu gab es im Gespräch keine Aussage.",
    "fr": "L'entretien n'a pas donné d'indication à ce sujet.",
    "it": "Nel colloquio non è emerso nulla su questo punto.",
}
NOT_OBSERVED["gsw"] = NOT_OBSERVED["de"]

# The evaluation criteria named in the challenge (docs/challenge.md): clarity, relevance, motivation,
# self-awareness, communication, concrete examples. Each one is a focus of at least one scored phase, so every
# interview gives evidence for all of them (tests/test_report.py checks this).
TASK_CRITERIA = ("clarity", "relevance", "motivation", "self_reflection", "communication", "concrete_examples")

# Criteria a phase usually gives evidence for: a hint for the analysis, and in the final report a low score only
# counts in a phase that asks for the criterion (report.final_scores).
PHASE_FOCUS = {
    "intro": ["clarity", "communication", "demeanor"],
    "motivation": ["motivation", "relevance", "goal_orientation", "preparation"],
    "strengths_weaknesses": ["self_reflection", "concrete_examples", "clarity"],
    "situational": ["concrete_examples", "difficult_questions", "clarity", "relevance", "communication"],
    "candidate_questions": ["initiative", "preparation", "communication"],
}


@lru_cache
def _rubric() -> dict:
    with open(RUBRIC_FILE, encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def criteria() -> dict[str, dict]:
    """Criterion key -> its entry in criteria.json, in rubric order."""
    return {c["key"]: c for c in _rubric()["criteria"]}


def keys() -> list[str]:
    return list(criteria())


def label(key: str, language: str) -> str:
    labels = criteria()[key]["label"]
    return labels.get("de" if language == "gsw" else language) or labels["en"]


def all_labels() -> dict[str, str]:
    """Every label in every language -> criterion key (to understand the model's keys)."""
    return {text: key for key, c in criteria().items() for text in c["label"].values()}


def describe(key: str) -> str:
    """One line for the prompt: what is assessed and the four levels (English)."""
    c = criteria()[key]
    levels = " | ".join(f"{level['value']} {level['description']['en']}" for level in c["levels"])
    return f"- {key} ({c['what_is_assessed']['en']}): {levels}"


def clamp(value: float) -> int:
    """The level for a mean score, rounded half up (2.5 -> 3). Python's round() rounds half to even (2.5 -> 2),
    which pulled every criterion with a mean of exactly x.5 down."""
    return max(SCALE_MIN, min(SCALE_MAX, math.floor(value + 0.5)))


def observed(scores: dict[str, Optional[int]]) -> dict[str, int]:
    return {key: value for key, value in scores.items() if value is not None}
