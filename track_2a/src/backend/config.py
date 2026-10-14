"""Setup options for the interview (GET /api/v1/config), loaded from data/ and the FHGR datasets/."""

import csv
import json
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OCCUPATIONS_CSV = Path(__file__).resolve().parents[2] / "datasets" / "occupations.csv"
POSTINGS_FILE = Path(__file__).resolve().parents[2] / "datasets" / "profiles" / "postings.jsonl"

GENERIC_OCCUPATION = "lehrstelle_allgemein"  # hidden entry in occupations.yaml, for apprenticeships given by name

LANGUAGES = [
    {"code": "de", "label": "Deutsch"},
    {"code": "fr", "label": "Français"},
    {"code": "it", "label": "Italiano"},
    {"code": "gsw", "label": "Schwiizerdütsch (Beta)"},
]

# Dialects for language "gsw" (the interviewer's dialect); the codes follow datasets/SCHEMA.md
DIALECTS = [
    {"code": "zh", "label": {"de": "Zürich", "fr": "Zurich", "it": "Zurigo"}},
    {"code": "be", "label": {"de": "Bern", "fr": "Berne", "it": "Berna"}},
    {"code": "bs", "label": {"de": "Basel", "fr": "Bâle", "it": "Basilea"}},
    {"code": "gr", "label": {"de": "Graubünden", "fr": "Grisons", "it": "Grigioni"}},
    {"code": "vs", "label": {"de": "Wallis", "fr": "Valais", "it": "Vallese"}},
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


@lru_cache
def _interviewer_voices() -> dict:
    with open(DATA_DIR / "interviewer_voices.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def interviewer_voice(posting_id: Optional[str]) -> str:
    """ "female" or "male": the voice for POST /speech, from data/interviewer_voices.yaml."""
    voices = _interviewer_voices()
    for voice in ("female", "male"):
        if posting_id in voices.get(voice, []):
            return voice
    return voices["default"]


# How the application letter shows which voice fits the contact person: the salutation before the name,
# or the grammatical form of the role ("Berufsbildnerin" / "Berufsbildner", "formatrice" / "formateur").
_SALUTATION = {"female": re.compile(r"^(frau|fr\.|madame|mme\.?|signora|sig\.ra)\s", re.I),
               "male": re.compile(r"^(herr|hr\.|monsieur|m\.|signor|sig\.)\s", re.I)}
_ROLE_ENDING = {"female": re.compile(r"(in|rice|euse|trice)$", re.I), "male": re.compile(r"(er|eur|ore)$", re.I)}


def contact_voice(name: str, role: str) -> str:
    """The voice for a contact person from the candidate's application letter, else the default."""
    role_word = (role.split(",")[0].split() or [""])[-1]
    for patterns, text in ((_SALUTATION, name.strip()), (_ROLE_ENDING, role_word)):
        for voice, pattern in patterns.items():
            if pattern.search(text):
                return voice
    return _interviewer_voices()["default"]


def posting_from_company(company: dict) -> dict:
    """A posting-shaped dict (like an FHGR posting) from the company details found in the candidate's application letter,
    or from a company Apertus invented at the start (interview/company.py, `generated: true`).

    All prompts work with this shape. From a letter only what the letter says is filled in; nothing is invented.
    Keys of `company`: name, place, contact_name, contact_role (and optionally about, apprentice_tasks, facts, generated).
    """
    about = company.get("about") or ""
    tasks = company.get("apprentice_tasks") or ""
    return {
        "id": None,
        "user_provided": not company.get("generated"),
        "company": {"name": company.get("name") or "", "place": company.get("place") or "", "description": about},
        "interviewer": {"name": company.get("contact_name") or "", "role": company.get("contact_role") or "",
                        "style": "friendly and professional",
                        "notes": "At the very start, briefly introduces themselves and the company, then asks the first question."},
        "offers": [],  # the tasks are in insider_facts; listing them twice made the answers repeat them
        "selection_process": [],
        # What a well-prepared candidate could know: everything the candidate told us about the company
        "insider_facts": [f for f in (about, f"Tasks in the apprenticeship: {tasks}" if tasks else "") if f]
                         + list(company.get("facts") or []),
    }


def posting_for(state: dict) -> Optional[dict]:
    """The company the interviewer works for: the candidate's own details, else the FHGR posting, else none."""
    if state.get("company"):
        return posting_from_company(state["company"])
    return postings().get(state.get("posting_id") or "")


def company_of(posting: Optional[dict]) -> Optional[dict]:
    """`company` of the API responses: name and place (null if there is no company name)."""
    if not posting or not posting["company"].get("name"):
        return None
    return {"name": posting["company"]["name"], "place": posting["company"].get("place") or ""}


# Interviewers for apprenticeships without an FHGR posting (or a letter without a contact person), so it is not
# always the same person. The role's ending gives the voice (contact_voice): "-in"/"-rice" female, "-er"/"-eur"/"-ore" male.
INTERVIEWERS = {
    "de": [("Sandra Keller", "Berufsbildnerin"), ("Marco Brunner", "Berufsbildner"), ("Nicole Frei", "Berufsbildnerin"),
           ("Thomas Huber", "Berufsbildner"), ("Lea Baumann", "Berufsbildnerin"), ("Daniel Gerber", "Berufsbildner")],
    "fr": [("Émilie Bovet", "Formatrice"), ("Yann Chappuis", "Formateur"), ("Céline Dubois", "Formatrice"),
           ("Mathieu Girard", "Formateur")],
    "it": [("Alessia Cattaneo", "Formatrice"), ("Paolo Ferrari", "Formatore"), ("Martina Rossi", "Formatrice"),
           ("Andrea Colombo", "Formatore")],
}


def random_interviewer(language: str) -> dict:
    """A name and role for the interviewer, picked at random (state key "persona")."""
    name, role = random.choice(INTERVIEWERS["de" if language == "gsw" else language])
    return {"name": name, "role": role}


def interviewer_of(posting: Optional[dict], persona: Optional[dict] = None) -> Optional[dict]:
    """`interviewer` of the API responses: the posting's contact person, else `persona`, else null."""
    if (not posting or not posting["interviewer"].get("name")) and persona:
        return {**persona, "voice": contact_voice(persona["name"], persona["role"])}
    if not posting or not posting["interviewer"].get("name"):
        return None
    name, role = posting["interviewer"]["name"], posting["interviewer"].get("role") or ""
    voice = interviewer_voice(posting["id"]) if posting.get("id") else contact_voice(name, role)
    return {"name": name, "role": role, "voice": voice}


def default_posting_id(occupation_id: str, language: str) -> Optional[str]:
    by_language = occupations()[occupation_id].get("postings") or {}
    return by_language.get("de" if language == "gsw" else language) or by_language.get("de")


# --- What the interviewer knows about an apprenticeship: datasets/occupations.csv (berufsberatung.ch) ------------

# Occupations of lehrberufe.ts that were renamed or merged: the name in the CSV is a different one
_RENAMED = {("winzer", "EFZ"): ("weinfachmann", "EFZ"), ("weintechnologe", "EFZ"): ("weinfachmann", "EFZ"),
            ("bodenleger", "EFZ"): ("boden-parkettleger", "EFZ")}


def _occupation_key(name: str) -> tuple[str, str]:
    """("Koch/Köchin EFZ") -> ("koch", "EFZ"): without the gender forms, so "Weintechnologe/-technologin" matches
    "Weintechnologe/-login" in the CSV."""
    qualification = re.search(r"\b(EFZ|EBA)\b", name)
    base = re.sub(r"\b(EFZ|EBA)\b", "", name).strip().lower()
    return re.sub(r"/-?[a-zäöüéèàç]+", "", base).strip(), qualification.group(1) if qualification else ""


@lru_cache
def _apprenticeships() -> tuple[dict, dict]:
    """The apprenticeships of the CSV by name key and by id (several rows of one name: the one with most tasks)."""
    by_key, by_id = {}, {}
    try:
        with open(OCCUPATIONS_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if not row["Bildungstypen"].startswith("Grundbildung"):
                    continue
                by_id[row["id"]] = row
                key = _occupation_key(row["Beruf"])
                if key not in by_key or len(row["Tätigkeiten"]) > len(by_key[key]["Tätigkeiten"]):
                    by_key[key] = row
    except OSError:
        pass  # without the data the interviewer only knows the name
    return by_key, by_id


def _words(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def _knowledge(row: Optional[dict]) -> str:
    """Typical tasks, duration and requirements of an apprenticeship as prompt text ("" if there is no row)."""
    if not row:
        return ""
    tasks = re.sub(r"^\s*Sie \w+ folgende Tätigkeiten aus:?", "", row["Tätigkeiten"]).strip()  # "üben" or "führen"
    duration = re.search(r"Dauer\s+(\d(?:\s*-\s*\d)?)\s+Jahre", row["Ausbildung"] or "")
    requirements = (row["Voraussetzungen"] or "").split("Anforderungen", 1)[-1]
    parts = [f"Typical tasks (from berufsberatung.ch): {_words(tasks, 520)}"] if tasks else []
    if duration:
        parts.append(f"Training duration: {duration.group(1)} years.")
    if requirements.strip():
        parts.append(f"Requirements: {_words(requirements, 260)}")
    return " ".join(parts)


def posting_for_name(name: str, language: str) -> Optional[str]:
    """An FHGR posting for the apprenticeship `name` (e.g. "Koch/Köchin EFZ") in the interview language, or None.

    With several postings (e.g. two Detailhandel companies) one is picked at random, for variety.
    """
    key, lang = _occupation_key(name), "de" if language == "gsw" else language
    matches = [p["id"] for p in postings().values()
               if p["lang"] == lang and _occupation_key(p["occupation"]["name_de"]) == key]
    return random.choice(matches) if matches else None


def occupation_knowledge(name: Optional[str] = None, csv_id: Optional[str] = None) -> str:
    """What is known about the apprenticeship `name` (e.g. "Koch/Köchin EFZ", the names of lehrberufe.ts) or the
    occupation with this id in occupations.csv. An empty string if the occupation is not in the data."""
    by_key, by_id = _apprenticeships()
    if csv_id and csv_id in by_id:
        return _knowledge(by_id[csv_id])
    if name:
        key = _occupation_key(name)
        return _knowledge(by_key.get(key) or by_key.get(_RENAMED.get(key, ("", ""))))
    return ""


def occupation_for(occupation_id: Optional[str], posting_id: Optional[str], occupation_name: Optional[str] = None) -> dict:
    """The occupation for the prompts: from the posting if there is one, else data/occupations.yaml.

    `occupation_name` (free text, e.g. "Koch/Köchin EFZ") is for occupations that are not in data/occupations.yaml:
    the interviewer then only knows the name, not the details of the apprenticeship.
    """
    posting = postings().get(posting_id or "")
    if not posting and occupation_name:
        knowledge = occupation_knowledge(occupation_name)
        return {"label": {"de": occupation_name, "fr": occupation_name, "it": occupation_name},
                "knowledge": bool(knowledge),
                "description": f"Swiss apprenticeship: {occupation_name}. {knowledge or 'Ask questions that fit this occupation; do not assume details of the training that you do not know.'}"}
    if not posting:
        occupation = occupations()[occupation_id]
        knowledge = occupation_knowledge(occupation["label"]["de"])
        return {**occupation, "description": f"{occupation['description'].strip()} {knowledge}".strip(),
                "knowledge": bool(knowledge)}
    o = posting["occupation"]
    intro = posting["posting_text"].split("\n\n")[1] if "\n\n" in posting["posting_text"] else posting["posting_text"]
    knowledge = occupation_knowledge(csv_id=str(o.get("occupation_id") or ""))
    return {"label": {"de": o["name_de"], "fr": o.get("name_fr"), "it": o.get("name_it")},
            "description": f"{intro[:400]} {knowledge}".strip(), "knowledge": bool(knowledge)}


def voice_config() -> dict:
    from backend.voice import stt, tts

    return {"stt": stt.enabled(), "tts": tts.engine()}


def public_config() -> dict:
    return {
        "languages": LANGUAGES,
        "occupations": [{"id": o["id"], "label": o["label"]} for o in occupations().values() if not o.get("hidden")],
        "interviewer_styles": [{"id": s["id"], "label": s["label"]} for s in interviewer_styles().values()],
        "modes": MODES,
        "voice": voice_config(),
        "dialects": DIALECTS,
        "postings": [{"id": p["id"], "lang": p["lang"], "occupation": p["occupation"]["name_de"],
                      "company": p["company"]["name"], "place": p["company"]["place"]} for p in postings().values()],
    }
