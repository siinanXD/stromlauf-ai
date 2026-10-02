"""Prompt-Caching im Agenten: Anthropic bekommt den Cache-Marker je Aufruf, OpenAI nicht (kein Parameter dafuer)."""

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent import graph as graph_module
from app.agent.prompts import SYSTEM_PROMPT


class _Bound:
    def __init__(self, log: list):
        self.log = log

    async def ainvoke(self, messages, config=None, **kwargs):
        self.log.append((messages, kwargs))
        return AIMessage(content="ok")


class _Model:
    def __init__(self, log: list):
        self.log = log

    def bind_tools(self, tools):
        return _Bound(self.log)


def _run(monkeypatch, model_name: str) -> tuple[list, dict]:
    log: list = []
    monkeypatch.setattr(graph_module, "make_chat_model", lambda name, **kwargs: _Model(log))
    graph = graph_module.build_graph(checkpointer=None)
    asyncio.run(
        graph.ainvoke(
            {"messages": [HumanMessage("Warum zieht -K1 nicht?")]},
            {"configurable": {"model": model_name, "source_ids": ["s1"]}},
        )
    )
    messages, kwargs = log[0]
    return messages, kwargs


def test_anthropic_bekommt_cache_marker(monkeypatch):
    messages, kwargs = _run(monkeypatch, "claude-sonnet-5")
    assert kwargs == {"cache_control": {"type": "ephemeral"}}
    assert isinstance(messages[0], SystemMessage) and messages[0].content == SYSTEM_PROMPT


def test_openai_bekommt_keinen_cache_marker(monkeypatch):
    _messages, kwargs = _run(monkeypatch, "openai:gpt-5-mini")
    assert kwargs == {}


def test_model_kwargs_for_kennt_die_provider():
    assert graph_module.model_kwargs_for("claude-haiku-4-5") == {
        "cache_control": {"type": "ephemeral"}
    }
    assert graph_module.model_kwargs_for("anthropic:claude-opus-5") == {
        "cache_control": {"type": "ephemeral"}
    }
    assert graph_module.model_kwargs_for("gpt-5.4-mini") == {}
