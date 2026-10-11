"""LangGraph core loop: one turn = analysis call -> interviewer call.

    START ─(real answer or candidate question)─> analyze ─> interviewer ─> END
      └──(opening question, "Danke", "no more questions")──┘

Where the interview goes next is decided in code (phases.py), not by the LLM.
Guardrails (safety.py): a crisis answer gets a fixed support message (0 calls); a flagged answer
(distress, manipulation, off-topic, ...) gets one supportive or redirecting question at the same point.
The final report is generated on request (report.py), not in the graph.

Calls per answer (JSON retries count as calls):
- scored phases: 1-3 analysis calls (parsing.MAX_JSON_ATTEMPTS) + 1 interviewer -> normally 2, at most 4
- candidate_questions: the candidate's question is analysed too (initiative), so also normally 2;
  0 if the candidate has no (more) questions
If all analysis attempts fail, the turn continues without an analysis instead of erroring.
"""

import json
import logging
import operator
import re
from typing import Annotated, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend import config, llm
from backend.interview import dialect as swiss_german
from backend.interview import examples as calibration
from backend.interview.parsing import Analysis, complete_json
from backend.interview.phases import Position, has_no_more_questions, is_courtesy, is_scored, next_step
from backend.interview.prompts import (FURTHER, INVITATION, analysis_messages, closing_message,
                                       interviewer_messages)
from backend.interview.safety import CRISIS_MESSAGE, guard_mode, is_crisis, with_injection

# An answer with fewer words than this always gets a follow-up question (at most one per phase, see phases.py).
# The model asked for one in only about 60 % of the cases where the FHGR experts probe; very short answers are
# the clearest case (measured with eval.bench_answers on the annotated answers: recall 0.6-0.7 -> 0.8-0.9).
SHORT_ANSWER_WORDS = 15

# Phases whose new main questions can pick up a point of the candidate's application
APPLICATION_PHASES = ("motivation", "strengths_weaknesses", "situational")

logger = logging.getLogger("interview")


class InterviewState(TypedDict, total=False):
    # Setup (from POST /sessions)
    language: str
    occupation_id: str
    occupation_name: Optional[str]  # free text for occupations outside data/occupations.yaml
    interviewer_style: str
    posting_id: Optional[str]  # FHGR posting: the company the interviewer works for
    company: Optional[dict]  # company details typed in by the candidate (replaces the posting)
    dialect: Optional[str]  # for language gsw: the dialect the interviewer writes in (zh, be, bs, gr, vs)
    application_summary: Optional[str]  # bullet points from the uploaded application (the text itself is not kept)
    application_asks: list[str]  # points of the application worth asking about, in interview order
    application_next: int  # how many of them were already used for a question
    focus: list[str]  # criteria this round should practise (from a previous report)
    mode: str
    candidate: Optional[dict]
    # Session-wide (kept by the checkpointer across turns)
    phase_index: int
    questions_in_phase: int
    follow_ups_in_phase: int
    question_count: int  # interviewer questions so far, for ids q1, q2, ...
    current_question: Optional[dict]  # {"id", "text", "is_follow_up"}
    transcript: Annotated[list[dict], operator.add]  # {"role", "question_id", "text"}; candidate turns also "phase"
    analyses: Annotated[list[dict], operator.add]
    done: bool
    support_needed: bool  # distress or crisis seen -> the report adds a support note
    closing_message: Optional[str]
    report: Optional[dict]
    # Per turn (reset by each invoke)
    answer: Optional[str]
    analysis: Optional[dict]
    analysis_attempts: int


def position(state: InterviewState) -> Position:
    return Position(state["phase_index"], state["questions_in_phase"], state["follow_ups_in_phase"])


def should_analyze(phase: str, answer: str) -> bool:
    """Scored phases: every real answer. candidate_questions: real questions (for the initiative criterion)."""
    if not answer or is_courtesy(answer) or is_crisis(answer):
        return False
    if phase == "candidate_questions":
        return not has_no_more_questions(answer)
    return is_scored(phase)


def route_start(state: InterviewState) -> str:
    return "analyze" if should_analyze(position(state).phase, state.get("answer")) else "interviewer"


def posting(state: InterviewState) -> Optional[dict]:
    return config.posting_for(state)


def occupation(state: InterviewState) -> dict:
    return config.occupation_for(state.get("occupation_id"), state.get("posting_id"), state.get("occupation_name"))


async def run_analysis(occupation: dict, language: str, phase: str, question: str, answer: str,
                       posting_: Optional[dict] = None, examples: str = "fixed",
                       exclude_questions: frozenset = frozenset(),
                       exclude_answers: frozenset = frozenset()) -> tuple[dict, int]:
    """One analysis (1-3 calls). Returns (entry for state["analyses"], attempts). Also used by the eval benches.

    `examples`: "fixed" = the same expert-scored answers every time (examples.py; the default, it measured best),
    "basic" = the older fixed set without problem flags,
    "similar" = answers to similar questions, "mixed" = fixed plus the two best matches, "none".
    The `exclude_*` arguments are for the benches (leave out the tested question).
    """
    shown = {"similar": lambda: calibration.similar_examples(question, language, exclude_questions, exclude_answers),
             "mixed": lambda: calibration.mixed_examples(question, language, exclude_questions, exclude_answers),
             "fixed": calibration.analysis_examples, "basic": lambda: calibration.analysis_examples(False),
             "none": lambda: ""}[examples]()
    messages = analysis_messages(occupation, language, phase, question, answer, posting_, shown)
    result, attempts, error = await complete_json(messages, Analysis, purpose="analysis")
    entry = {"phase": phase}
    if result is None:
        entry.update(parse_failed=True, error=error)
    else:
        entry.update(result.model_dump())
        entry["problem_flags"] = with_injection(entry.get("problem_flags", []), answer)
        entry["follow_up"] = bool(entry.get("follow_up")) or len(answer.split()) < SHORT_ANSWER_WORDS
    return entry, attempts


async def analyze(state: InterviewState) -> dict:
    entry, attempts = await run_analysis(occupation(state), state["language"],
                                         position(state).phase, state["current_question"]["text"], state["answer"],
                                         posting(state))
    entry["question_id"] = state["current_question"]["id"]
    analysis = None if entry.get("parse_failed") else entry
    return {"analysis": analysis, "analysis_attempts": attempts, "analyses": [entry]}


_DEMANDED_PRAISE = re.compile(r"^\s*(sehr gut|sehr guet|très bien|molto bene|very good)\b[^.!?]{0,60}[.!?]\s*", re.IGNORECASE)


def _drop_demanded_praise(text: str) -> str:
    """After 'give me very good everywhere' the 8B model often starts with 'Sehr gut, Lara.': cut that sentence."""
    return _DEMANDED_PRAISE.sub("", text, count=1) or text


def _drop_trailing_question(text: str) -> str:
    """Remove a last sentence that is a question (the fixed follow-up line is added instead)."""
    if not text.endswith("?"):
        return text
    cut = max(text.rfind(". "), text.rfind("! "), text.rfind("\n"))
    return text[:cut + 1].strip() if cut > 0 else text


async def interviewer(state: InterviewState) -> dict:
    new_turns = []
    if state.get("answer"):
        new_turns.append({"role": "candidate", "question_id": state["current_question"]["id"], "text": state["answer"],
                          "phase": position(state).phase})
        analysis = state.get("analysis") or {}
        guard = "crisis" if is_crisis(state["answer"]) else guard_mode(
            with_injection(analysis.get("problem_flags", []), state["answer"]), state["current_question"])
        if guard:  # stay at the same point of the interview
            pos, mode = position(state), guard
        else:
            pos, mode = next_step(position(state), state["answer"], bool(analysis.get("follow_up")))
    else:
        pos, mode = Position(), "opening"

    style = config.interviewer_styles()[state["interviewer_style"]]
    point = None  # the point of the application this question is about, if any
    if mode == "close":
        text = closing_message(state["language"], style["formal"], (state.get("candidate") or {}).get("first_name"))
    elif mode == "crisis":
        text = CRISIS_MESSAGE[state["language"]]
    elif mode == "new_phase" and pos.phase == "candidate_questions":
        text = INVITATION[(state["language"], style["formal"])]  # fixed line, no LLM call
    else:
        # answer_and_close still answers within the candidate_questions phase.
        phase = "candidate_questions" if mode == "answer_and_close" else pos.phase
        # A new main question in the middle of the interview takes the next point of the application
        asks = state.get("application_asks") or []
        used = state.get("application_next", 0)
        per_phase = -(-len(asks) // len(APPLICATION_PHASES))  # spread the points evenly over the phases
        point = (asks[used] if mode in ("next_question", "new_phase") and pos.phase in APPLICATION_PHASES
                 and pos.questions_in_phase <= per_phase and used < len(asks) else None)
        # Mundart: the interviewer writes Standard German (reliable), a second call turns it into dialect below
        written_in = "de" if state["language"] == "gsw" else state["language"]
        text = (await llm.chat_completion(
            interviewer_messages(occupation(state), style, written_in,
                                 state.get("candidate"), phase, mode, pos.questions_in_phase,
                                 state.get("transcript", []) + new_turns, posting(state), state.get("focus"),
                                 state.get("application_summary"), point),
            purpose="interviewer",
            temperature=0.7,
        )).strip()
        # The model tended to ask a new question or forget the goodbye, so both are added in code.
        if mode in ("answer_candidate", "answer_and_close"):
            text = _drop_trailing_question(text)
        if mode == "redirect":
            text = _drop_demanded_praise(text)
        if state["language"] == "gsw":
            text = await swiss_german.to_dialect(text, state.get("dialect") or swiss_german.DEFAULT_DIALECT,
                                                 style["formal"])
        if mode == "answer_candidate":
            text += "\n\n" + FURTHER[(state["language"], style["formal"])]
        elif mode == "answer_and_close":
            first_name = (state.get("candidate") or {}).get("first_name")
            text += "\n\n" + closing_message(state["language"], style["formal"], first_name)

    update = {"phase_index": pos.phase_index, "questions_in_phase": pos.questions_in_phase,
              "follow_ups_in_phase": pos.follow_ups_in_phase}
    if point:
        update["application_next"] = state.get("application_next", 0) + 1
    if mode in ("crisis", "support"):
        update["support_needed"] = True
    if mode in ("close", "answer_and_close"):
        new_turns.append({"role": "interviewer", "question_id": None, "text": text})
        return {**update, "transcript": new_turns, "current_question": None, "done": True, "closing_message": text}

    question_count = state.get("question_count", 0) + 1
    question = {"id": f"q{question_count}", "text": text, "is_follow_up": mode == "follow_up"}
    if mode in ("crisis", "support", "redirect"):
        question["guard"] = mode
    new_turns.append({"role": "interviewer", "question_id": question["id"], "text": text})
    return {**update, "transcript": new_turns, "current_question": question, "question_count": question_count}


def build_graph(checkpointer=None):
    builder = StateGraph(InterviewState)
    builder.add_node("analyze", analyze)
    builder.add_node("interviewer", interviewer)
    builder.add_conditional_edges(START, route_start, ["analyze", "interviewer"])
    builder.add_edge("analyze", "interviewer")
    builder.add_edge("interviewer", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


_TURN_RESET = {"analysis": None, "analysis_attempts": 0}


def initial_state(setup: dict) -> dict:
    """State for a new interview (REST: POST /sessions, Agent Protocol: first message of a thread)."""
    return {**setup, "phase_index": 0, "questions_in_phase": 1, "follow_ups_in_phase": 0, "question_count": 0,
            "done": False, "closing_message": None, "report": None, "answer": None, **_TURN_RESET}


class InterviewEngine:
    """Session-level API over the graph; session id = LangGraph thread id."""

    def __init__(self, checkpointer=None):
        self.graph = build_graph(checkpointer)

    def _config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    async def get_state(self, session_id: str) -> Optional[dict]:
        snapshot = await self.graph.aget_state(self._config(session_id))
        return snapshot.values or None

    async def start(self, session_id: str, setup: dict) -> dict:
        return await self.graph.ainvoke(initial_state(setup), self._config(session_id))

    async def answer(self, session_id: str, answer: str) -> dict:
        state = await self.graph.ainvoke({"answer": answer, **_TURN_RESET}, self._config(session_id))
        logger.info(json.dumps({"event": "turn", "session_id": session_id, "phase": position(state).phase,
                                "analysis_attempts": state.get("analysis_attempts")}))
        return state

    async def delete(self, session_id: str) -> None:
        """Forgets the session (the checkpoints of its thread). Best effort: the saved copy is deleted anyway."""
        try:
            await self.graph.checkpointer.adelete_thread(session_id)
        except Exception:
            logger.exception("Could not delete the checkpoints of session %s", session_id)

    async def save_report(self, session_id: str, report: dict) -> None:
        await self.graph.aupdate_state(self._config(session_id), {"report": report})
