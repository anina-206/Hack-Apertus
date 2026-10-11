"""The Agent Protocol graph `agent` (agent.py), run in-process with a checkpointer and the fake LLM."""

import asyncio

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from backend import agent
from backend.tests.test_graph import fake  # noqa: F401  (fixture)


class Chat:
    """One thread, like a client of the Agent Protocol: send a message, get the new AI messages."""

    def __init__(self, **configurable):
        self.graph = agent.build_agent_graph().compile(checkpointer=InMemorySaver())
        self.config = {"configurable": {"thread_id": "t1", **configurable}}
        self.seen = 0

    def send(self, text: str) -> list[str]:
        state = asyncio.run(self.graph.ainvoke({"messages": [{"role": "user", "content": text}]}, self.config))
        new = state["messages"][self.seen:]
        self.seen = len(state["messages"])
        self.state = state
        return [m.content for m in new if isinstance(m, AIMessage)]


def run_to_end(chat: Chat, answer="Ich baue gerne PCs zusammen.") -> list[str]:
    replies = []
    while not chat.state.get("done"):
        text = "Nein, danke." if chat.state["phase_index"] == 4 else answer  # candidate_questions
        replies = chat.send(text)
    return replies


def test_whole_interview_by_chat(fake):
    fake()
    chat = Chat(occupation_id="informatiker_efz")
    assert chat.send("Hallo!") == ["Frage 1?"]  # the first message starts the interview
    assert chat.state["posting_id"] == "P-11" and chat.state["mode"] == "rehearsal"
    replies = run_to_end(chat)
    assert replies[0].startswith("Vielen Dank")  # fixed goodbye
    feedback = replies[-1]
    assert "## Dein Feedback" in feedback and "Klarheit: 3/4" in feedback and "Gesamtwert" in feedback
    assert chat.state["report"]["overall_score"] == 3.0
    assert chat.send("Danke!") == [agent.FINISHED["de"]]  # after the end: no new interview, no LLM call


def test_language_and_occupation_from_the_first_message(fake):
    fake()
    chat = Chat()
    chat.send("Bonjour, je suis Léa et je postule comme coiffeuse.")
    assert chat.state["language"] == "fr" and chat.state["posting_id"] == "P-17"


def test_unknown_occupation_uses_the_generic_one(fake):
    client = fake()
    chat = Chat()
    chat.send("Hallo, ich bin Lara.")
    assert chat.state["occupation_id"] == agent.DEFAULT_OCCUPATION and chat.state["posting_id"] is None
    assert "ask which apprenticeship" in client.last_system


def test_training_mode_sends_the_tip_before_the_next_question(fake):
    fake()
    chat = Chat(occupation_id="kv_efz", language="it", mode="training")
    chat.send("Buongiorno")
    replies = chat.send("Mi chiamo Lara e mi piace organizzare.")
    assert replies == ["Consiglio: Nenne ein Beispiel.", "Frage 3?"]


def test_match_posting():
    assert agent.match_posting("Ich bewerbe mich als Konstrukteurin bei euch.", "de") == "P-01"
    assert agent.match_posting("Je voudrais devenir horloger.", "fr") == "P-19"
    assert agent.match_posting("Hallo zusammen", "de") is None
