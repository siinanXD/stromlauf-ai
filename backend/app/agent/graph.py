"""LangGraph-Agent: Modell <-> Werkzeuge in einer Schleife, Gespraechsverlauf per Checkpointer."""

from functools import lru_cache

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.prompts import system_prompt_for
from app.agent.tools import TOOLS
from app.config import get_settings
from app.llm import make_chat_model


def _build_model(model_name: str):
    return make_chat_model(model_name, max_tokens=32000, max_retries=3, streaming=True).bind_tools(TOOLS)


def model_name_for(config: dict | None) -> str:
    """Modell dieser Anfrage (configurable.model aus dem Chat-Body, z. B. fuer Evals) oder CHAT_MODEL."""
    configurable = (config or {}).get("configurable") or {}
    return configurable.get("model") or get_settings().chat_model


def build_graph(checkpointer):
    # Lazy und je Modellname, damit das Backend ohne Schluessel startet (Upload/Verwaltung geht trotzdem)
    get_model = lru_cache(maxsize=8)(_build_model)

    async def agent(state: MessagesState, config: RunnableConfig) -> dict:
        messages = [SystemMessage(system_prompt_for(config.get("configurable"))), *state["messages"]]
        return {"messages": [await get_model(model_name_for(config)).ainvoke(messages, config)]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)
