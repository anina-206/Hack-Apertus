"""Setup options for the interview (GET /api/v1/config), loaded from data/ and the FHGR datasets/."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
POSTINGS_FILE = Path(__file__).resolve().parents[2] / "datasets" / "profiles" / "postings.jsonl"

LANGUAGES = [
    {"code": "de", "label": "Deutsch"},
    {"code": "fr", "label": "Français"},
    {"code": "it", "label": "Italiano"},
    {"code": "gsw", "label": "Schwiizerdütsch (Beta)"},
]

MODES = [
    {"id": "training", "description": "Short feedback after every answer"},
    {"id": "rehearsal", "description": "Realistic, feedback only at the end"},
]


def _load(name: str) -> list[dict]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def occupations() -> dict[str, dict]:
    return {o["id"]: o for o in _load("occupations.yaml")}


@lru_cache
def interviewer_styles() -> dict[str, dict]:
    return {s["id"]: s for s in _load("interviewer_styles.yaml")}


@lru_cache
def postings() -> dict[str, dict]:
    """FHGR apprenticeship postings (fictional companies): the company the interviewer works for."""
    with open(POSTINGS_FILE, encoding="utf-8") as f:
        return {p["id"]: p for p in (json.loads(line) for line in f if line.strip())}


def default_posting_id(occupation_id: str, language: str) -> Optional[str]:
    by_language = occupations()[occupation_id].get("postings") or {}
    return by_language.get("de" if language == "gsw" else language) or by_language.get("de")


def occupation_for(occupation_id: Optional[str], posting_id: Optional[str]) -> dict:
    """The occupation for the prompts: from the posting if there is one (any of the 30), else data/occupations.yaml."""
    posting = postings().get(posting_id or "")
    if not posting:
        return occupations()[occupation_id]
    o = posting["occupation"]
    intro = posting["posting_text"].split("\n\n")[1] if "\n\n" in posting["posting_text"] else posting["posting_text"]
    return {"label": {"de": o["name_de"], "fr": o.get("name_fr"), "it": o.get("name_it")}, "description": intro[:400]}


def public_config() -> dict:
    return {
        "languages": LANGUAGES,
        "occupations": [{"id": o["id"], "label": o["label"]} for o in occupations().values() if not o.get("hidden")],
        "interviewer_styles": [{"id": s["id"], "label": s["label"]} for s in interviewer_styles().values()],
        "modes": MODES,
        "postings": [{"id": p["id"], "lang": p["lang"], "occupation": p["occupation"]["name_de"],
                      "company": p["company"]["name"], "place": p["company"]["place"]} for p in postings().values()],
    }
