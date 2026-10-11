"""Guess the language of a text (de / fr / it) from frequent short words. Good enough for whole answers."""

import re

STOPWORDS = {
    "de": {"und", "ich", "du", "die", "der", "das", "nicht", "mit", "ist", "dein", "deine", "hast", "wie", "auch",
           "bin", "mich", "habe", "gerne"},
    "fr": {"et", "je", "tu", "le", "la", "les", "pas", "avec", "est", "ton", "ta", "tes", "as", "une", "des",
           "suis", "moi", "bonjour"},
    "it": {"e", "io", "tu", "il", "la", "non", "con", "è", "che", "tuo", "tua", "hai", "una", "per", "di",
           "sono", "mi", "buongiorno"},
}


def detect(text: str, default: str = "de") -> str:
    words = re.findall(r"\w+", text.lower())
    counts = {lang: sum(w in stop for w in words) for lang, stop in STOPWORDS.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] else default
