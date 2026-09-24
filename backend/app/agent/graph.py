"""LangGraph-Agent: Modell <-> Werkzeuge in einer Schleife, Gespraechsverlauf per Checkpointer."""

from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.config import get_settings


def _build_model():
    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.chat_model,
        api_key=settings.anthropic_api_key,
        max_tokens=32000,
        max_retries=3,
        streaming=True,
    )
    return llm.bind_tools(TOOLS)


def build_graph(checkpointer):
    # Lazy, damit das Backend auch ohne ANTHROPIC_API_KEY startet (Upload/Verwaltung geht trotzdem)
    get_model = lru_cache(maxsize=1)(_build_model)

    async def agent(state: MessagesState, config: RunnableConfig) -> dict:
        messages = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [await get_model().ainvoke(messages, config)]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)
