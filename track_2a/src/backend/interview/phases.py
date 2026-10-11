"""Phase logic: decides in code (not by the LLM) where the interview goes next.

Phases: intro -> motivation -> strengths_weaknesses -> situational
        -> candidate_questions -> closing

Scored phases ask a fixed number of main questions, plus at most one
follow-up when the analysis says the answer was vague. In
candidate_questions the candidate asks and the interviewer answers; this
phase is not scored and ends when the candidate has no more questions or
after MAX_CANDIDATE_TURNS. Keeping this deterministic makes interviews
consistent across runs.
"""

import re
from dataclasses import dataclass
from typing import Literal

PHASE_ORDER = ["intro", "motivation", "strengths_weaknesses", "situational", "candidate_questions", "closing"]

# Main questions per scored phase (follow-ups come on top).
# 11 scored + the invitation to ask questions = 12 main questions (FHGR: a session has 10-15 plus follow-ups).
QUESTIONS_PER_PHASE = {"intro": 2, "motivation": 3, "strengths_weaknesses": 3, "situational": 3}
MAX_FOLLOW_UPS_PER_PHASE = 1
MAX_CANDIDATE_TURNS = 2

SCORED_PHASES = set(QUESTIONS_PER_PHASE)

# Main questions in the whole interview: the scored ones plus the invitation to ask questions.
TOTAL_QUESTIONS = sum(QUESTIONS_PER_PHASE.values()) + 1

Mode = Literal["follow_up", "next_question", "new_phase", "answer_candidate", "answer_and_close", "close"]

# Short replies meaning "no (more) questions" in DE/CH/FR/IT/EN.
_NO_MORE_QUESTIONS = re.compile(
    r"\b(nein|nei|nö|keine|kei|nüt|nichts|alles klar|non|rien|aucune|nessuna|niente|nulla|no|none|nope)\b",
    re.IGNORECASE,
)

# Pure courtesy replies ("Danke!", "Vielen Dank für das Gespräch", "Merci beaucoup") carry nothing to score:
# every word is from this list.
_COURTESY_WORDS = set(
    "danke dank dankeschön vielen herzlichen merci vielmal für das gespräch auch ok okay super gern gerne "
    "beaucoup pour l'entretien de rien thanks thank you grazie mille per il colloquio prego".split()
)


@dataclass(frozen=True)
class Position:
    phase_index: int = 0
    questions_in_phase: int = 1  # main questions asked so far in this phase
    follow_ups_in_phase: int = 0

    @property
    def phase(self) -> str:
        return PHASE_ORDER[self.phase_index]


def progress(pos: Position) -> dict:
    """Main question number out of TOTAL_QUESTIONS. Follow-ups and candidate-question turns don't advance it."""
    if pos.phase in SCORED_PHASES:
        current = sum(QUESTIONS_PER_PHASE[p] for p in PHASE_ORDER[: pos.phase_index]) + pos.questions_in_phase
    else:
        current = TOTAL_QUESTIONS
    return {"current": current, "total": TOTAL_QUESTIONS}


def is_scored(phase: str) -> bool:
    return phase in SCORED_PHASES


def is_courtesy(answer: str) -> bool:
    words = re.findall(r"[\w']+", answer.lower())
    return 0 < len(words) <= 6 and all(word in _COURTESY_WORDS for word in words)


def has_no_more_questions(answer: str) -> bool:
    """True for short replies like "Nein, danke" that contain no question."""
    text = answer.strip()
    return "?" not in text and len(text.split()) <= 8 and bool(_NO_MORE_QUESTIONS.search(text))


def next_step(pos: Position, answer: str, wants_follow_up: bool) -> tuple[Position, Mode]:
    """Where to go after the candidate's `answer` at position `pos`."""
    if pos.phase == "candidate_questions":
        if has_no_more_questions(answer):
            return _advance(pos), "close"
        if pos.questions_in_phase >= MAX_CANDIDATE_TURNS:
            return _advance(pos), "answer_and_close"
        return Position(pos.phase_index, pos.questions_in_phase + 1, 0), "answer_candidate"

    if wants_follow_up and pos.follow_ups_in_phase < MAX_FOLLOW_UPS_PER_PHASE:
        return Position(pos.phase_index, pos.questions_in_phase, pos.follow_ups_in_phase + 1), "follow_up"
    if pos.questions_in_phase < QUESTIONS_PER_PHASE[pos.phase]:
        return Position(pos.phase_index, pos.questions_in_phase + 1, pos.follow_ups_in_phase), "next_question"
    return _advance(pos), "new_phase"


def _advance(pos: Position) -> Position:
    return Position(pos.phase_index + 1, 1, 0)
