"""A fictional training company for apprenticeships without an FHGR posting, written by Apertus at the start.

Only 34 of the about 250 apprenticeships have a posting (datasets/profiles/postings.jsonl). For all others one LLM
call at POST /sessions invents a small company, so the interviewer can talk about "our company" and answer the
candidate's questions. The interviewer's name and the town are picked in code (variety, and the voice fits the
name); the model only writes the company. If the call fails, the interview starts without a company.
"""

import random
from typing import Optional

from backend import llm
from backend.interview.prompts import LANGUAGES

# Towns per language region; Mundart uses the region of the dialect.
TOWNS = {
    "de": ["Winterthur", "Aarau", "Luzern", "St. Gallen", "Thun", "Baden", "Zug", "Olten", "Frauenfeld", "Chur",
           "Solothurn", "Wil", "Uster", "Burgdorf"],
    "fr": ["Lausanne", "Fribourg", "Sion", "Neuchâtel", "Yverdon-les-Bains", "Bulle", "Delémont", "Genève", "Morges"],
    "it": ["Lugano", "Bellinzona", "Locarno", "Mendrisio", "Biasca", "Chiasso", "Roveredo"],
}
DIALECT_TOWNS = {"zh": ["Zürich", "Winterthur", "Uster"], "be": ["Bern", "Thun", "Burgdorf"],
                 "bs": ["Basel", "Liestal"], "gr": ["Chur", "Davos", "Landquart"], "vs": ["Brig", "Visp"]}

MAX_FACTS = 4
NOT_GIVEN = {"", "none", "n/a", "-"}


def town(language: str, dialect: Optional[str] = None) -> str:
    if language == "gsw" and dialect in DIALECT_TOWNS:
        return random.choice(DIALECT_TOWNS[dialect])
    return random.choice(TOWNS["de" if language == "gsw" else language])


def parse(raw: str) -> dict:
    """COMPANY / ABOUT / TASKS lines and '- ' facts -> {"name", "about", "apprentice_tasks", "facts"}."""
    keys = {"COMPANY": "name", "ABOUT": "about", "TASKS": "apprentice_tasks"}
    company, facts = {}, []
    for line in raw.splitlines():
        stripped = line.strip().lstrip("*• ").strip()
        key, _, value = stripped.partition(":")
        value = value.strip().strip("\"'«»").strip()
        if key.strip().upper() in keys:
            if value.lower() not in NOT_GIVEN:
                company[keys[key.strip().upper()]] = value[:300]
        elif stripped.startswith("-") and stripped.lstrip("- ").strip():
            facts.append(stripped.lstrip("- ").strip()[:200])
    company["facts"] = facts[:MAX_FACTS]
    return company if company.get("name") else {}


async def generate(occupation: dict, language: str, place: str, contact_name: str, contact_role: str) -> dict:
    """One LLM call. Returns the company in the shape of config.posting_from_company, or {} if nothing usable came."""
    written_in = "de" if language == "gsw" else language
    system = (
        "You invent a small, realistic, FICTIONAL Swiss company that trains apprentices, for a practice job "
        "interview of a school student.\n"
        f"Apprenticeship: {occupation['label']['de']} ({occupation['description'].strip()[:600]})\n"
        f"The company is in {place}. The person who conducts the interview is {contact_name}, {contact_role}.\n"
        "Do not use the name of a real company. Write exactly these lines, the keys in English, the values in "
        f"{LANGUAGES[written_in]}:\n"
        "COMPANY: the company name (short, sounds Swiss, fits the occupation)\n"
        "ABOUT: two sentences: what the company does, how big it is, what is special about it\n"
        "TASKS: one sentence: what apprentices do there\n"
        "Then 3 or 4 lines starting with '- ', each a concrete fact a well-prepared candidate could know (e.g. a "
        "project of the apprentices, working hours, a special machine or product, how many apprentices).\n"
        "Output only these lines."
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": "Write the lines now."}]
    raw = await llm.chat_completion(messages, purpose="company", temperature=0.8, max_tokens=400)
    company = parse(raw.strip())
    if company:
        company.update(place=place, contact_name=contact_name, contact_role=contact_role, generated=True)
    return company
