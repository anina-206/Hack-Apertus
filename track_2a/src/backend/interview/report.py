"""Final report (GET /sessions/{id}/report): numbers from code, texts from one LLM call.

FHGR rubric: 11 criteria, 1-4, or null when the interview showed nothing about it.
Scores, overall score and next_practice are computed from the per-answer
analyses, so they are consistent and can't be hallucinated. The LLM only
writes comments, strengths and improvements. Evidence quotes are kept only
if they really appear in the candidate's answers.
"""

import json
import logging
import re
from statistics import mean
from typing import Optional

from backend import config
from backend.interview.parsing import ReportDraft, complete_json
from backend.interview import rubric, safety
from backend.interview.phases import has_no_more_questions
from backend.interview.prompts import CRITERIA, report_messages


logger = logging.getLogger("interview")


class ReportUnavailable(RuntimeError):
    pass


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'„“”«»‘’]", "", text)).strip().lower()


def _verified_evidence(quote: str, candidate_texts: list[str]) -> str:
    quote = quote.strip().strip("\"'„“”«»…. ")
    if quote and any(_norm(quote) in _norm(text) for text in candidate_texts):
        return quote
    return ""


def final_scores(state: dict) -> tuple[dict[str, int], dict[str, float]]:
    """Score per observed criterion (rounded mean, 1-4) and the unrounded means (for ranking).

    Criteria no answer gave evidence for are left out (not observed). Exception: if the
    candidate reached the question round and asked nothing, initiative is 1 (rubric level 1:
    "No questions at the end").
    """
    analyses = [a for a in state.get("analyses", []) if not a.get("parse_failed")]
    means = {}
    for key in CRITERIA:
        values = [a["scores"][key] for a in analyses if a["scores"].get(key) is not None]
        if values:
            means[key] = mean(values)
    asked = any(t["role"] == "candidate" and t.get("phase") == "candidate_questions"
                and not has_no_more_questions(t["text"]) for t in state.get("transcript", []))
    if "initiative" not in means and state.get("done") and not asked:
        means["initiative"] = rubric.SCALE_MIN
    return {key: rubric.clamp(value) for key, value in means.items()}, means


async def build_report(session_id: str, state: dict, occupation: Optional[dict] = None) -> dict:
    """`occupation` defaults to the session's occupation from data/occupations.yaml (the benches pass their own)."""
    scores, means = final_scores(state)
    analyses = [a for a in state.get("analyses", []) if not a.get("parse_failed")]
    transcript = state.get("transcript", [])
    candidate_texts = [t["text"] for t in transcript if t["role"] == "candidate"]

    draft: Optional[ReportDraft]
    draft, _, error = await complete_json(
        report_messages(occupation or config.occupation_for(state.get("occupation_id"), state.get("posting_id")),
                        state["language"], scores,
                        analyses, transcript, config.postings().get(state.get("posting_id") or "")),
        ReportDraft,
        purpose="report",
        temperature=0.4,
        max_tokens=2500,
    )
    if draft is None:
        raise ReportUnavailable(f"Report could not be generated: {error}")

    missing = [key for key in scores if not (draft.criteria.get(key) and draft.criteria[key].comment)]
    if missing:
        logger.warning(json.dumps({"event": "report_comments_missing", "session_id": session_id, "criteria": missing}))

    language = state["language"]
    # The model sometimes forgets a list: fall back to the tips from the per-answer analyses
    improvements = [i.model_dump() for i in draft.improvements]
    if not improvements:
        tips = list(dict.fromkeys(a["short_tip"] for a in scored if a.get("short_tip")))[:3]
        improvements = [{"tip": tip, "example_answer": ""} for tip in tips]

    labels = CRITERIA_LABELS[state["language"]]
    criteria = []
    for key in CRITERIA:  # all 11 in rubric order; not observed ones have score None
        note = draft.criteria.get(key) if key in scores else None
        criteria.append({
            "id": key,
            "label": rubric.label(key, language),
            "score": scores.get(key),
            "comment": (note.comment if note else "") if key in scores else rubric.NOT_OBSERVED[language],
            "evidence": _verified_evidence(note.evidence, candidate_texts) if note else "",
        })

    return {
        "session_id": session_id,
        "language": language,
        "scale": {"min": rubric.SCALE_MIN, "max": rubric.SCALE_MAX},
        # Average of the shown scores of the observed criteria, so the overall score matches the bars.
        "overall_score": round(mean(scores.values()), 1) if scores else None,
        "criteria": criteria,
        "strengths": draft.strengths,
        "improvements": [i.model_dump() for i in draft.improvements],
        "next_practice": sorted(means, key=lambda k: means[k])[:2],
        "closing": draft.closing,
        # FHGR rule L3: point to a real person when the interview showed distress.
        "support_note": safety.SUPPORT_NOTE[language] if _distress(state) else None,
        "improvements": improvements,
        "next_practice": sorted(averages, key=lambda k: averages[k])[:2],
    }


def _distress(state: dict) -> bool:
    flagged = any(safety.SUPPORT_FLAGS & set(a.get("problem_flags", [])) for a in state.get("analyses", []))
    return flagged or bool(state.get("support_needed"))
