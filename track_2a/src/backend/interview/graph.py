"""LangGraph core loop: one turn = analysis call -> interviewer call.

    START ─(answer in scored phase)─> analyze ─> interviewer ─> END
      └──(opening question, or candidate_questions phase)──┘

Where the interview goes next is decided in code (phases.py), not by the LLM.
The final report is generated on request (report.py), not in the graph.

Calls per answer (JSON retries count as calls):
- scored phases: 1-3 analysis calls (parsing.MAX_JSON_ATTEMPTS) + 1 interviewer -> normally 2, at most 4
- candidate_questions: 1 interviewer call, or 0 if the candidate has no (more) questions
If all analysis attempts fail, the turn continues without an analysis instead of erroring.
"""

import json
import logging
import operator
from typing import Annotated, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend import config, llm
from backend.interview.parsing import Analysis, complete_json
from backend.interview.phases import Position, is_scored, next_step
from backend.interview.prompts import (FURTHER, INVITATION, analysis_messages, closing_message,
                                       interviewer_messages)

logger = logging.getLogger("interview")


class InterviewState(TypedDict, total=False):
    # Setup (from POST /sessions)
    language: str
    occupation_id: str
    interviewer_style: str
    mode: str
    candidate: Optional[dict]
    # Session-wide (kept by the checkpointer across turns)
    phase_index: int
    questions_in_phase: int
    follow_ups_in_phase: int
    question_count: int  # interviewer questions so far, for ids q1, q2, ...
    current_question: Optional[dict]  # {"id", "text", "is_follow_up"}
    transcript: Annotated[list[dict], operator.add]  # {"role": "interviewer"|"candidate", "question_id", "text"}
    analyses: Annotated[list[dict], operator.add]
    done: bool
    closing_message: Optional[str]
    report: Optional[dict]
    # Per turn (reset by each invoke)
    answer: Optional[str]
    analysis: Optional[dict]
    analysis_attempts: int


def position(state: InterviewState) -> Position:
    return Position(state["phase_index"], state["questions_in_phase"], state["follow_ups_in_phase"])


def route_start(state: InterviewState) -> str:
    return "analyze" if state.get("answer") and is_scored(position(state).phase) else "interviewer"


async def analyze(state: InterviewState) -> dict:
    phase = position(state).phase
    messages = analysis_messages(config.occupations()[state["occupation_id"]], state["language"],
                                 state["current_question"]["text"], state["answer"])
    result, attempts, error = await complete_json(messages, Analysis, purpose="analysis")
    entry = {"phase": phase, "question_id": state["current_question"]["id"]}
    if result is None:
        entry.update(parse_failed=True, error=error)
        return {"analysis": None, "analysis_attempts": attempts, "analyses": [entry]}
    entry.update(result.model_dump())
    return {"analysis": entry, "analysis_attempts": attempts, "analyses": [entry]}


def _drop_trailing_question(text: str) -> str:
    """Remove a last sentence that is a question (the fixed follow-up line is added instead)."""
    if not text.endswith("?"):
        return text
    cut = max(text.rfind(". "), text.rfind("! "), text.rfind("\n"))
    return text[:cut + 1].strip() if cut > 0 else text


async def interviewer(state: InterviewState) -> dict:
    new_turns = []
    if state.get("answer"):
        new_turns.append({"role": "candidate", "question_id": state["current_question"]["id"], "text": state["answer"]})
        wants_follow_up = bool((state.get("analysis") or {}).get("follow_up"))
        pos, mode = next_step(position(state), state["answer"], wants_follow_up)
    else:
        pos, mode = Position(), "opening"

    style = config.interviewer_styles()[state["interviewer_style"]]
    if mode == "close":
        text = closing_message(state["language"], style["formal"], (state.get("candidate") or {}).get("first_name"))
    elif mode == "new_phase" and pos.phase == "candidate_questions":
        text = INVITATION[(state["language"], style["formal"])]  # fixed line, no LLM call
    else:
        # answer_and_close still answers within the candidate_questions phase.
        phase = "candidate_questions" if mode == "answer_and_close" else pos.phase
        text = (await llm.chat_completion(
            interviewer_messages(config.occupations()[state["occupation_id"]], style, state["language"],
                                 state.get("candidate"), phase, mode, pos.questions_in_phase,
                                 state.get("transcript", []) + new_turns),
            purpose="interviewer",
            temperature=0.7,
        )).strip()
        # The model tended to ask a new question or forget the goodbye, so both are added in code.
        if mode in ("answer_candidate", "answer_and_close"):
            text = _drop_trailing_question(text)
        if mode == "answer_candidate":
            text += "\n\n" + FURTHER[(state["language"], style["formal"])]
        elif mode == "answer_and_close":
            first_name = (state.get("candidate") or {}).get("first_name")
            text += "\n\n" + closing_message(state["language"], style["formal"], first_name)

    update = {"phase_index": pos.phase_index, "questions_in_phase": pos.questions_in_phase,
              "follow_ups_in_phase": pos.follow_ups_in_phase}
    if mode in ("close", "answer_and_close"):
        new_turns.append({"role": "interviewer", "question_id": None, "text": text})
        return {**update, "transcript": new_turns, "current_question": None, "done": True, "closing_message": text}

    question_count = state.get("question_count", 0) + 1
    question = {"id": f"q{question_count}", "text": text, "is_follow_up": mode == "follow_up"}
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
        initial = {**setup, "phase_index": 0, "questions_in_phase": 1, "follow_ups_in_phase": 0,
                   "question_count": 0, "done": False, "closing_message": None, "report": None,
                   "answer": None, **_TURN_RESET}
        return await self.graph.ainvoke(initial, self._config(session_id))

    async def answer(self, session_id: str, answer: str) -> dict:
        state = await self.graph.ainvoke({"answer": answer, **_TURN_RESET}, self._config(session_id))
        logger.info(json.dumps({"event": "turn", "session_id": session_id, "phase": position(state).phase,
                                "analysis_attempts": state.get("analysis_attempts")}))
        return state

    async def save_report(self, session_id: str, report: dict) -> None:
        await self.graph.aupdate_state(self._config(session_id), {"report": report})
