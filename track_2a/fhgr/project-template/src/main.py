from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import BaseMessage, add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

load_dotenv()


class BaseState(BaseModel):
    messages: Annotated[list, add_messages]


def create_graph() -> CompiledStateGraph:

    def node_one(state: BaseState):
        input_message: BaseMessage = state.messages[-1]  # Last message in the state

        return {"messages": [AIMessage(content=input_message.content)]}

    graph_builder = StateGraph(BaseState)

    graph_builder.add_node("node_one", node_one)

    graph_builder.add_edge(START, "node_one")
    graph_builder.add_edge("node_one", END)

    graph = graph_builder.compile(debug=False)

    print(graph.get_graph().draw_ascii())

    return graph


graph = create_graph()
