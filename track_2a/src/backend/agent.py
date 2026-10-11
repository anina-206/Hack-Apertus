"""Graph `agent` for Aegra / the Agent Protocol (the FHGR project template's interface): chat in, chat out.

One thread = one interview. The same nodes as the REST API (interview/graph.py) do the work;
this graph only translates between chat messages and the interview state:

    START -> receive ─(new thread)──────────────────────────> interviewer -> respond -> END
                     ├(answer)──> analyze (if scored) ──────> interviewer -> respond -> END
                     └(interview already over)──> finished ─────────────────────────> END

- First message of a thread: starts the interview, the reply is the opening question.
- Every further message is one answer. The reply is the next question; in training mode a
  short tip comes first.
- When the interview ends, the reply is the goodbye followed by the final feedback (report).

Setup comes from the run's config.configurable (all optional): language, occupation_id,
posting_id, interviewer_style, mode, candidate, focus. Without them, the language is guessed
from the first message and the occupation is matched against the 30 FHGR postings.
Aegra provides the checkpointer (Postgres), so the graph is compiled without one.
"""

import re
from typing import Annotated, Optional

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from backend import config
from backend.interview import language as lang
from backend.interview import rubric
from backend.interview.graph import (_TURN_RESET, InterviewState, analyze, initial_state, interviewer,
                                     route_start)
from backend.interview.report import ReportUnavailable, build_report

DEFAULT_OCCUPATION = "lehrstelle_allgemein"  # hidden entry in data/occupations.yaml

FINISHED = {
    "de": "Das Interview ist beendet, dein Feedback steht oben. Für ein neues Interview starte einen neuen Chat.",
    "fr": "L'entretien est terminé, ton feedback se trouve plus haut. Pour un nouvel entretien, commence un nouveau chat.",
    "it": "Il colloquio è finito, il tuo feedback è qui sopra. Per un nuovo colloquio inizia una nuova chat.",
}
FINISHED["gsw"] = FINISHED["de"]

HEADINGS = {
    "de": {"feedback": "Dein Feedback", "overall": "Gesamtwert", "strengths": "Das kannst du schon gut",
           "improvements": "So wirst du noch besser", "example": "Beispiel", "next": "Das übst du als Nächstes",
           "said": "Du hast gesagt", "tip": "Tipp", "not_observed": "Noch keine Aussage zu"},
    "fr": {"feedback": "Ton feedback", "overall": "Évaluation globale", "strengths": "Ce que tu fais déjà bien",
           "improvements": "Pour t'améliorer encore", "example": "Exemple", "next": "À travailler ensuite",
           "said": "Tu as dit", "tip": "Conseil", "not_observed": "Pas encore observé"},
    "it": {"feedback": "Il tuo feedback", "overall": "Valutazione globale", "strengths": "Cosa fai già bene",
           "improvements": "Per migliorare ancora", "example": "Esempio", "next": "Da esercitare ora",
           "said": "Hai detto", "tip": "Consiglio", "not_observed": "Non ancora osservato"},
}
HEADINGS["gsw"] = HEADINGS["de"]


class AgentState(InterviewState, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    after_end: bool  # a message arrived after the interview was over


def _text(message: AnyMessage) -> str:
    content = message.content
    if isinstance(content, list):  # content parts, e.g. [{"type": "text", "text": "..."}]
        content = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content).strip()


def _last_human(state: AgentState) -> str:
    return next((_text(m) for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")


# Generic words in occupation names that say nothing about the occupation.
_GENERIC = {"fachmann", "fachfrau", "assistent", "assistentin", "frau", "mann", "gesundheit"}


def match_posting(text: str, language: str) -> Optional[str]:
    """The FHGR posting whose occupation is named in the text (e.g. "als Konstrukteur"), if any."""
    words = set(re.findall(r"\w+", text.lower()))
    best, best_hits = None, 0
    for pid, posting in config.postings().items():
        names = " ".join(v for k, v in posting["occupation"].items() if k.startswith("name_") and v)
        stems = {w[:7] for w in re.findall(r"\w+", names.lower()) if len(w) > 5 and w not in _GENERIC}
        hits = sum(1 for w in words if len(w) > 5 and w[:7] in stems)
        hits += 0.5 if hits and posting["lang"] == ("de" if language == "gsw" else language) else 0
        if hits > best_hits:
            best, best_hits = pid, hits
    return best


def setup_from(configurable: dict, first_message: str) -> dict:
    language = configurable.get("language") or lang.detect(first_message)
    posting_id = configurable.get("posting_id")
    occupation_id = configurable.get("occupation_id")
    if not posting_id and occupation_id:
        posting_id = config.default_posting_id(occupation_id, language)
    if not posting_id and not occupation_id:
        posting_id = match_posting(first_message, language)
    return {
        "language": language,
        "occupation_id": occupation_id or (None if posting_id else DEFAULT_OCCUPATION),
        "posting_id": posting_id,
        "interviewer_style": configurable.get("interviewer_style", "friendly"),
        "mode": configurable.get("mode", "rehearsal"),
        "candidate": configurable.get("candidate"),
        "focus": configurable.get("focus", []),
    }


async def receive(state: AgentState, config: RunnableConfig) -> dict:
    text = _last_human(state)
    if "phase_index" not in state:  # first message of the thread
        return {**initial_state(setup_from(config.get("configurable", {}), text)), "after_end": False}
    if state.get("done"):
        return {"after_end": True}
    return {"answer": text or "...", "after_end": False, **_TURN_RESET}


def route_receive(state: AgentState) -> str:
    return "finished" if state.get("after_end") else route_start(state)


def format_report(report: dict, language: str) -> str:
    """The report as one chat message (Markdown)."""
    h, scale = HEADINGS[language], report["scale"]["max"]
    lines = []
    if report.get("support_note"):
        lines += [report["support_note"], ""]
    lines.append(f"## {h['feedback']}")
    if report["overall_score"] is not None:
        lines.append(f"**{h['overall']}: {report['overall_score']} / {scale}**")
    lines.append("")
    for c in report["criteria"]:
        if c["score"] is None:
            continue
        lines.append(f"- **{c['label']}: {c['score']}/{scale}**. {c['comment']}")
        if c.get("evidence"):
            lines.append(f"  {h['said']}: «{c['evidence']}»")
    missing = [c["label"] for c in report["criteria"] if c["score"] is None]
    if missing:
        lines += ["", f"{h['not_observed']}: {', '.join(missing)}"]
    lines += ["", f"### {h['strengths']}"] + [f"- {s}" for s in report["strengths"]]
    lines += ["", f"### {h['improvements']}"]
    for item in report["improvements"]:
        lines.append(f"- {item['tip']}")
        if item.get("example_answer"):
            lines.append(f"  {h['example']}: {item['example_answer']}")
    if report["next_practice"]:
        lines += ["", f"**{h['next']}:** " + ", ".join(rubric.label(k, language) for k in report["next_practice"])]
    if report.get("closing"):
        lines += ["", report["closing"]]
    return "\n".join(lines)


async def respond(state: AgentState, config: RunnableConfig) -> dict:
    """Turn the interviewer's new turn (and at the end the report) into chat messages."""
    language = state["language"]
    messages = []
    analysis = state.get("analysis")
    if state.get("mode") == "training" and analysis and analysis.get("short_tip"):
        messages.append(AIMessage(content=f"{HEADINGS[language]['tip']}: {analysis['short_tip']}"))
    messages.append(AIMessage(content=state["transcript"][-1]["text"]))
    if not state.get("done"):
        return {"messages": messages}
    thread_id = config.get("configurable", {}).get("thread_id", "agent")
    try:
        report = await build_report(str(thread_id), state)
    except ReportUnavailable:
        return {"messages": messages}  # the next message to the thread retries the report (see finished)
    messages.append(AIMessage(content=format_report(report, language)))
    return {"messages": messages, "report": report}


async def finished(state: AgentState, config: RunnableConfig) -> dict:
    language = state["language"]
    if state.get("report"):
        return {"messages": [AIMessage(content=FINISHED[language])]}
    report = await build_report(str(config.get("configurable", {}).get("thread_id", "agent")), state)
    return {"messages": [AIMessage(content=format_report(report, language))], "report": report}


def build_agent_graph():
    builder = StateGraph(AgentState)
    builder.add_node("receive", receive)
    builder.add_node("analyze", analyze)
    builder.add_node("interviewer", interviewer)
    builder.add_node("respond", respond)
    builder.add_node("finished", finished)
    builder.add_edge(START, "receive")
    builder.add_conditional_edges("receive", route_receive, ["analyze", "interviewer", "finished"])
    builder.add_edge("analyze", "interviewer")
    builder.add_edge("interviewer", "respond")
    builder.add_edge("respond", END)
    builder.add_edge("finished", END)
    return builder


# Aegra loads this (aegra.json "graphs": {"agent": "./src/backend/agent.py:graph"}) and adds its checkpointer.
graph = build_agent_graph().compile()
