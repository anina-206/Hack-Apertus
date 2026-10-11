"""Deterministic checks on a report (no LLM): the problems found in the first manual test, made measurable."""

import re

from backend.interview import language

# Formal address or third person instead of du/tu (the coach always uses informal address).
# German "Sie" at the start of a sentence can mean "she/they", so only capitalised forms inside a sentence count.
_FORMAL = {
    "de": re.compile(r"(?<![.!?:]\s)(?<!^)\b(Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem)\b"),
    "fr": re.compile(r"\b(vous|votre|vos)\b", re.IGNORECASE),
    "it": re.compile(r"\b(Lei|Suo|Sua|Suoi)\b"),
}
_THIRD_PERSON = {
    "de": re.compile(r"\b(der Kandidat|die Kandidatin|man)\b", re.IGNORECASE),
    "fr": re.compile(r"\b(le candidat|la candidate)\b", re.IGNORECASE),
    "it": re.compile(r"\b(il candidato|la candidata)\b", re.IGNORECASE),
}
for _patterns in (_FORMAL, _THIRD_PERSON):
    _patterns["gsw"] = _patterns["de"]

_MOJIBAKE = re.compile(r"[ÃÂ][\u0080-¿]")


def report_texts(report: dict) -> list[str]:
    texts = [c["comment"] for c in report["criteria"] if c.get("score") is not None]
    texts += report.get("strengths", [])
    for item in report.get("improvements", []):
        texts += [item.get("tip", ""), item.get("example_answer", "")]
    return [t for t in texts if t]


def detected_language(text: str) -> str:
    return language.detect(text)


def check_report(report: dict, language: str) -> dict:
    """Counts of problems in one report. 0 everywhere = clean."""
    observed = [c for c in report["criteria"] if c.get("score") is not None]
    texts = report_texts(report)
    expected = "de" if language == "gsw" else language
    # Example answers are what the candidate would say, so they may use "Sie" towards the company.
    coach_texts = [c["comment"] for c in observed] + report.get("strengths", []) + \
        [i.get("tip", "") for i in report.get("improvements", [])]
    return {
        "empty_comments": sum(1 for c in observed if not c.get("comment", "").strip()),
        "formal_or_third_person": sum(len(_FORMAL[language].findall(t)) + len(_THIRD_PERSON[language].findall(t))
                                      for t in coach_texts),
        "mojibake": sum(len(_MOJIBAKE.findall(t)) for t in texts),
        "wrong_language": int(bool(texts) and detected_language(" ".join(texts)) != expected),
        "evidence_share": round(sum(1 for c in observed if c.get("evidence")) / len(observed), 2) if observed else None,
        "observed_criteria": len(observed),
    }


def summarise(checks: list[dict]) -> dict:
    """Share of reports with each problem, plus the average evidence share."""
    if not checks:
        return {}
    keys = ["empty_comments", "formal_or_third_person", "mojibake", "wrong_language"]
    summary = {f"reports_with_{k}": round(sum(1 for c in checks if c[k]) / len(checks), 2) for k in keys}
    shares = [c["evidence_share"] for c in checks if c["evidence_share"] is not None]
    summary["evidence_share_avg"] = round(sum(shares) / len(shares), 2) if shares else None
    return summary
