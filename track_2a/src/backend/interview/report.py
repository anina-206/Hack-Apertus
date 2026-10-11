"""Final report (GET /sessions/{id}/report): numbers from code, texts from one LLM call.

Scores, overall score and next_practice are computed from the per-answer
analyses, so they are consistent and can't be hallucinated. The LLM only
writes comments, strengths and improvements. Evidence quotes are kept only
if they really appear in the candidate's answers.
"""

import re
from statistics import mean
from typing import Optional

from backend import config
from backend.interview.parsing import ReportDraft, complete_json
from backend.interview.prompts import CRITERIA, CRITERIA_LABELS, report_messages


class ReportUnavailable(RuntimeError):
    pass


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'„“”«»‘’]", "", text)).strip().lower()


def _verified_evidence(quote: str, candidate_texts: list[str]) -> str:
    quote = quote.strip().strip("\"'„“”«»…. ")
    if quote and any(_norm(quote) in _norm(text) for text in candidate_texts):
        return quote
    return ""


async def build_report(session_id: str, state: dict) -> dict:
    scored = [a for a in state.get("analyses", []) if not a.get("parse_failed")]
    averages = {key: mean(a["scores"][key] for a in scored) for key in CRITERIA} if scored else {}
    transcript = state.get("transcript", [])
    candidate_texts = [t["text"] for t in transcript if t["role"] == "candidate"]

    draft: Optional[ReportDraft]
    draft, _, error = await complete_json(
        report_messages(config.occupations()[state["occupation_id"]], state["language"], averages, scored, transcript),
        ReportDraft,
        purpose="report",
        temperature=0.4,
        max_tokens=2500,
    )
    if draft is None:
        raise ReportUnavailable(f"Report could not be generated: {error}")

    # The model sometimes forgets a list: fall back to the tips from the per-answer analyses
    improvements = [i.model_dump() for i in draft.improvements]
    if not improvements:
        tips = list(dict.fromkeys(a["short_tip"] for a in scored if a.get("short_tip")))[:3]
        improvements = [{"tip": tip, "example_answer": ""} for tip in tips]

    labels = CRITERIA_LABELS[state["language"]]
    criteria = []
    for key, avg in averages.items():
        note = draft.criteria.get(key)
        criteria.append({
            "id": key,
            "label": labels[key],
            "score": max(1, min(5, round(avg))),
            "comment": note.comment if note else "",
            "evidence": _verified_evidence(note.evidence, candidate_texts) if note else "",
        })

    return {
        "session_id": session_id,
        "language": state["language"],
        "overall_score": round(mean(averages.values()), 1) if averages else None,
        "criteria": criteria,
        "strengths": draft.strengths,
        "improvements": improvements,
        "next_practice": sorted(averages, key=lambda k: averages[k])[:2],
    }
