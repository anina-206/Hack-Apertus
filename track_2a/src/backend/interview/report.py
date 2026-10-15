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
from difflib import SequenceMatcher
from statistics import mean
from typing import Optional

from backend import config
from backend.interview import parsing, rubric, safety
from backend.interview.parsing import CriterionNote, ReportDraft, complete_json
from backend.interview.phases import has_no_more_questions
from backend.interview.prompts import CRITERIA, report_messages


logger = logging.getLogger("interview")


class ReportUnavailable(RuntimeError):
    pass


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'„“”«»‘’]", "", text)).strip().lower()


_WORD = re.compile(r"\w+")

# A quote counts if this share of its words appears close together in one answer (at least MIN_QUOTE_WORDS words)
QUOTE_MATCH = 0.7
MIN_QUOTE_WORDS = 3


def _verified_evidence(quote: str, candidate_texts: list[str]) -> str:
    """The quote as the candidate really said it, or "" if they did not say it.

    The 8B model rarely quotes word for word ("Ich mag Mathe" for "Mathe mag ich schon"), so an exact
    match kept no quote at all (bench_transcripts: evidence share 0). Now it is enough that most of the
    quote's words appear close together in one answer; the evidence shown is that part of the answer, so it is
    always what the candidate said.
    """
    quote = quote.strip().strip("\"'„“”«»…. ")
    if not quote:
        return ""
    if any(_norm(quote) in _norm(text) for text in candidate_texts):
        return quote
    wanted = [w.lower() for w in _WORD.findall(quote)]
    best, best_text, best_span = 0, "", (0, 0)
    for text in candidate_texts:
        words = list(_WORD.finditer(text))
        blocks = [b for b in SequenceMatcher(None, [w.group().lower() for w in words], wanted,
                                             autojunk=False).get_matching_blocks() if b.size]
        matched = sum(b.size for b in blocks)
        if not blocks or matched <= best:
            continue
        first, last = blocks[0].a, blocks[-1].a + blocks[-1].size - 1
        if last - first + 1 <= 2 * len(wanted):  # the words must be close together, not spread over the answer
            best, best_text, best_span = matched, text, (words[first].start(), words[last].end())
    if best >= max(MIN_QUOTE_WORDS, QUOTE_MATCH * len(wanted)):
        return best_text[best_span[0]:best_span[1]]
    return ""


# "Der Kandidat verknüpft ...", "Er zeigt ...": the report must speak to the candidate (du/tu), not about them.
_THIRD_PERSON = re.compile(
    r"\b(der|die|dem|den) (kandidat|kandidatin|bewerber|bewerberin)\b|(^|[.!] )(er|sie) [a-zäöü]+t\b|"
    r"\b(le|la) (candidat|candidate)\b|"
    r"\b(il|la) candidat[oa]\b",
    re.IGNORECASE,
)
_THIRD_PERSON_FIX = ("IMPORTANT: Write every text directly to the candidate with 'du' (fr/it: 'tu'), e.g. 'Du hast ...'. "
                     "Never write 'der Kandidat', 'er' or 'sie' about them.")

# An example answer is what the candidate could say ("Ich ..."), not a description of what is missing.
_FIRST_PERSON = re.compile(r"\b(ich|mir|mich|mein\w*|je|j'|moi|mon|ma|mes|io|mi|il mio|la mia)\b", re.IGNORECASE)


def _texts(draft: ReportDraft) -> list[str]:
    return ([draft.closing, *draft.strengths] + [i.tip for i in draft.improvements]
            + [n.comment for n in draft.criteria.values()])


def _in_third_person(draft: ReportDraft) -> bool:
    return any(_THIRD_PERSON.search(text) for text in _texts(draft) if text)


# From this score on, an answer counts for a criterion in every phase (it shows the criterion even where it was not asked)
POSITIVE_EVIDENCE = 3


def counts_for(key: str, score: int, phase: Optional[str]) -> bool:
    """Whether an answer's score for a criterion goes into the final score.

    The model also scored criteria an answer was not about, mostly low (on 48 FHGR answers it rated
    concrete_examples 17 times where the experts did not, e.g. "concrete examples: 1" for a greeting). Such
    scores pulled the report down. So a low score only counts in a phase that asks for the criterion
    (rubric.PHASE_FOCUS); a good one counts everywhere. Every challenge criterion is a focus of a scored phase,
    so each one is still judged with its low scores (rubric.TASK_CRITERIA).
    """
    return score >= POSITIVE_EVIDENCE or phase is None or key in rubric.PHASE_FOCUS.get(phase, ())


# From this many criteria without a comment the report is asked once more (it is the only call at the end,
# so the limit of calls per answer is not touched).
MANY_MISSING = 3


def _missing_comments(draft: ReportDraft, scores: dict) -> list[str]:
    """Observed criteria without a comment, after reading lost ones from the raw text of the last call."""
    missing = [key for key in scores if not (draft.criteria.get(key) and draft.criteria[key].comment)]
    if missing:  # read them from the raw text, where the JSON repair lost them
        rescued = parsing.criteria_from_raw(parsing.last_raw)
        draft.criteria.update({key: rescued[key] for key in missing if key in rescued})
        missing = [key for key in missing if key not in rescued]
    return missing


# The French reports that broke off had written é as \u00e9 and then repeated \u00a0 until the token limit
# (bench_transcripts T-12, twice in a row).
_NO_ESCAPES = ("IMPORTANT: Write letters like é, à and ü directly, never as \\u escapes. Keep every comment to one "
               "or two short sentences.")


def _analysis_tip(key: str, analyses: list[dict]) -> str:
    """The short tip of the answer with the lowest score on this criterion (written per answer, in the same language)."""
    scored = [a for a in analyses if a["scores"].get(key) is not None and a.get("short_tip")]
    return min(scored, key=lambda a: a["scores"][key])["short_tip"] if scored else ""


def final_scores(state: dict) -> tuple[dict[str, int], dict[str, float]]:
    """Score per observed criterion (rounded mean, 1-4) and the unrounded means (for ranking).

    Criteria no answer gave evidence for are left out (not observed). Exception: if the
    candidate reached the question round and asked nothing, initiative is 1 (rubric level 1:
    "No questions at the end").
    """
    analyses = [a for a in state.get("analyses", []) if not a.get("parse_failed")]
    means = {}
    for key in CRITERIA:
        values = [a["scores"][key] for a in analyses
                  if a["scores"].get(key) is not None and counts_for(key, a["scores"][key], a.get("phase"))]
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

    messages = report_messages(occupation or config.occupation_for(state.get("occupation_id"), state.get("posting_id"),
                                                                  state.get("occupation_name")),
                               state["language"], scores, analyses, transcript, config.posting_for(state))
    draft: Optional[ReportDraft]
    def ask():
        # No frequency_penalty here: it also penalises the JSON keys and the quotes, which repeat by design
        # (bench_transcripts with 0.3: quotes dropped from 75 % to 33 %, "Nächstes Mal" turned into "Nechtest").
        return complete_json(messages, ReportDraft, purpose="report", temperature=0.4, max_tokens=2500)

    draft, _, error = await ask()
    if draft is None:
        raise ReportUnavailable(f"Report could not be generated: {error}")
    if _in_third_person(draft):  # one more try; the first draft is kept if the second is no better
        messages[0] = {**messages[0], "content": messages[0]["content"] + "\n" + _THIRD_PERSON_FIX}
        retry, _, _ = await ask()
        if retry is not None and not _in_third_person(retry):
            draft = retry

    missing = _missing_comments(draft, scores)
    if len(missing) >= MANY_MISSING:  # the output broke off (repetition loop): one more try, keep the better one
        messages[0] = {**messages[0], "content": messages[0]["content"] + "\n" + _NO_ESCAPES}
        retry, _, _ = await ask()
        retry_missing = _missing_comments(retry, scores) if retry is not None else missing
        if len(retry_missing) < len(missing):
            draft, missing = retry, retry_missing
    for key in missing:  # last resort: the analysis tip of the answer that scored lowest on this criterion
        tip = _analysis_tip(key, analyses)
        if tip:
            draft.criteria[key] = CriterionNote(comment=tip, evidence="")
    if missing:
        # With the raw output, to see whether the model left them out or the parser lost them
        logger.warning(json.dumps({"event": "report_comments_missing", "session_id": session_id, "criteria": missing,
                                   "raw": parsing.last_raw}, ensure_ascii=False))

    language = state["language"]
    # The model sometimes forgets a list: fall back to the tips from the per-answer analyses
    improvements = [i.model_dump() for i in draft.improvements]
    if not improvements:
        tips = list(dict.fromkeys(a["short_tip"] for a in analyses if a.get("short_tip")))[:3]
        improvements = [{"tip": tip, "example_answer": ""} for tip in tips]
    for item in improvements:
        # Italian drops the subject pronoun ("Ho fatto uno stage"), so the check only works for DE/FR
        if language != "it" and not _FIRST_PERSON.search(item["example_answer"]):
            item["example_answer"] = ""

    rejected = {key: note.evidence for key, note in draft.criteria.items()
                if key in scores and note.evidence.strip() and not _verified_evidence(note.evidence, candidate_texts)}
    if rejected:  # quotes the candidate did not say (to tune _verified_evidence)
        logger.warning(json.dumps({"event": "evidence_rejected", "session_id": session_id, "quotes": rejected},
                               ensure_ascii=False))

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
        "improvements": improvements,
        "next_practice": sorted(means, key=lambda k: means[k])[:2],
        "closing": draft.closing,
        # Feedback on the uploaded application letter (made at the start of the interview), else null
        "application_feedback": state.get("application_review"),
        # FHGR rule L3: point to a real person when the interview showed distress.
        "support_note": safety.SUPPORT_NOTE[language] if _distress(state) else None,
    }


def _distress(state: dict) -> bool:
    flagged = any(safety.SUPPORT_FLAGS & set(a.get("problem_flags", [])) for a in state.get("analyses", []))
    return flagged or bool(state.get("support_needed"))
