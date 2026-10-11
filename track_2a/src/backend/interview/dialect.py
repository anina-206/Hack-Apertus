"""Swiss German (Mundart): the interviewer writes Standard German first, a second call turns it into dialect.

Apertus 8B answers in Standard German when it is asked to interview in dialect, and it mixes the examples into the
text when they are given in the interview prompt. Translating a finished text is much more reliable: the model gets
parallel examples (Standard German -> dialect) and only has to convert. The examples come from the FHGR question
bank (datasets/questions: the same question in Zürich, Bern, Basel, Graubünden and Valais dialect) plus a few
typical interviewer phrases. The dialect texts have not been reviewed by native speakers (FHGR flags them too).
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from backend import llm

logger = logging.getLogger("interview")

QUESTIONS_FILE = Path(__file__).resolve().parents[3] / "datasets" / "questions" / "questions.jsonl"

# code -> name in German (the UI uses the labels from config.py)
DIALECTS = {"zh": "Zürichdeutsch", "be": "Berndeutsch", "bs": "Baseldeutsch", "gr": "Bündnerdeutsch", "vs": "Walliserdeutsch"}
DEFAULT_DIALECT = "zh"

# Typical phrases of an interviewer that the question bank does not contain (praise, thanks, transitions).
PHRASES = {
    "zh": [
        ("Das klingt toll, Lara!", "Das tönt super, Lara!"),
        ("Danke für deine Antwort.", "Merci für dini Antwort."),
        ("Erzähl mir doch ein bisschen von dir.", "Verzell mer doch es bitzeli öppis vo dir."),
        ("Was machst du, wenn du nicht weiterkommst?", "Was machsch, wänn du nöd wiiterchunsch?"),
        ("Kannst du mir ein Beispiel nennen?", "Chasch mer es Bispiil nenne?"),
        ("Wie bist du darauf gekommen, diesen Beruf zu lernen?", "Wie bisch uf die Idee cho, de Bruef z lehre?"),
        ("Das ist eine gute Frage. Ich freue mich, dich kennenzulernen.", "Das isch e gueti Frag. Ich fröi mi, dich känne z lehre."),
    ],
    "be": [
        ("Das klingt toll, Lara!", "Das tönt super, Lara!"),
        ("Danke für deine Antwort.", "Merci für di Antwort."),
        ("Erzähl mir doch ein bisschen von dir.", "Verzeu mir doch es bitzeli öppis vo dir."),
        ("Was machst du, wenn du nicht weiterkommst?", "Was machsch, wenn du nid witerchunsch?"),
        ("Kannst du mir ein Beispiel nennen?", "Chasch mir es Bispiu nenne?"),
        ("Wie bist du darauf gekommen, diesen Beruf zu lernen?", "Wie bisch uf die Idee cho, dä Bruef z lehre?"),
        ("Das ist eine gute Frage. Ich freue mich, dich kennenzulernen.", "Das isch e gueti Frag. I fröie mi, di chennezlehre."),
    ],
}

EXAMPLES_FROM_QUESTIONS = 8
MAX_GROWTH = 3  # a translation longer than this many times the original is not a translation

# Words that Standard German does not have. Only a rough check (every word starting with "ch" counts too, except
# the few Standard German ones), not a quality measure: dialect has no fixed spelling.
_MARKERS = {
    "isch", "nöd", "nüd", "nid", "nit", "hesch", "bisch", "chasch", "chli", "gärn", "gäll", "öppis", "öppe", "gsi", "gha",
    "händ", "hät", "chönd", "mached", "wotsch", "wosch", "dä", "dr", "dini", "mini", "dis", "mis", "din", "wiä", "bruef",
    "bruuche", "tönt", "tönd", "hüt", "bitzeli", "bitzli", "bitzi", "bissi", "schuel", "schueu", "freiziit", "freizyt",
    "wännsch", "wänn", "wenn's", "zäme", "zämme", "machsch", "denksch", "chönsch", "verzell", "verzeu", "erzell", "erzeu",
    "fründe", "gueti", "guet", "aagfange", "aafange", "möchtisch", "möchtsch", "weli", "wele", "mer", "öis", "eus", "vo",
}
_NOT_MARKERS = {"vo", "mer"}  # too often in other languages or names: not counted alone
_CH_STANDARD = {"chef", "chefin", "chor", "charakter", "chance", "chancen", "chemie", "china", "chip", "chat", "check", "checkliste"}


def markers(text: str) -> int:
    """How many different words of the text are typical for Swiss German (0 for Standard German)."""
    words = set(re.findall(r"[a-zäöüéèàç']+", text.lower()))
    typical = {w for w in words if w in _MARKERS - _NOT_MARKERS}
    starts_with_ch = {w for w in words if w.startswith("ch") and w not in _CH_STANDARD}
    return len(typical | starts_with_ch)


def looks_like_dialect(text: str) -> bool:
    return markers(text) >= 2


@lru_cache
def _question_pairs(dialect: str) -> list[tuple[str, str]]:
    """Standard German question -> the same question in the dialect, evenly picked from the FHGR question bank."""
    pairs = []
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        for line in f:
            q = json.loads(line) if line.strip() else {}
            variant = {v["dialect"]: v["text"] for v in q.get("gsw_variants") or []}.get(dialect)
            if variant and len(variant) <= 110:
                pairs.append((q["text"]["de"], variant))
    step = max(1, len(pairs) // EXAMPLES_FROM_QUESTIONS)
    return pairs[::step][:EXAMPLES_FROM_QUESTIONS]


def examples(dialect: str) -> list[tuple[str, str]]:
    return PHRASES.get(dialect, []) + _question_pairs(dialect)


def messages(text: str, dialect: str, formal: bool) -> list[dict]:
    name = DIALECTS[dialect]
    shots = "\n".join(f"Standard German: {de}\n{name}: {gsw}" for de, gsw in examples(dialect))
    address = 'Keep the formal "Sie" (dialect: "Sie").' if formal else 'Address the person with "du".'
    system = (
        f"You translate Standard German into Swiss German dialect ({name}), written the way Swiss people write in "
        "chats (phonetic spelling, e.g. isch, nöd, chli, gärn, hesch, bisch, öppis, gsi). Change every word that is "
        f"not dialect. Keep names, the meaning and the number of sentences. {address}\n"
        f"Examples:\n{shots}\n"
        f"Output only the {name} text, nothing else."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": text}]


async def to_dialect(text: str, dialect: str, formal: bool = False) -> str:
    """The text in dialect; the Standard German text if the call fails or returns nonsense."""
    if dialect not in DIALECTS:
        dialect = DEFAULT_DIALECT
    try:
        raw = await llm.chat_completion(messages(text, dialect, formal), purpose="dialect", temperature=0.2)
    except Exception:
        logger.exception("Dialect translation failed, keeping Standard German")
        return text
    translated = re.sub(r"^\s*(Swiss German|Standard German|[A-Za-zü]+deutsch)\s*(\([^)]*\))?\s*:\s*", "", raw.strip(), flags=re.IGNORECASE)
    translated = translated.strip().strip('"«»')
    if not translated or len(translated) > MAX_GROWTH * len(text) + 80:
        return text
    return translated
