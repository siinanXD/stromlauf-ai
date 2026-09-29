"""Verlauf eines Chats (GET /api/conversations/{id}/messages): LangGraph-Nachrichten -> MessageOut (Issue #47)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.api.chat import _history

REFS = [
    {
        "document_id": "d1",
        "filename": "01_Stromlaufplan_FB-01.pdf",
        "doc_type": "schematic",
        "page": 3,
        "section": "Hauptstromkreis",
    },
    {
        "document_id": "d2",
        "filename": "02_Stueckliste_FB-01.xlsx",
        "doc_type": "bom",
        "page": None,
        "section": "",
    },
]


def _exchange(question: str, answer: str, refs: list[dict]) -> list:
    return [
        HumanMessage(question),
        AIMessage(
            content="", tool_calls=[{"name": "find_tag", "args": {"tag": "-F2"}, "id": "c1"}]
        ),
        ToolMessage(content="Fundstellen ...", tool_call_id="c1", artifact=refs),
        AIMessage(content=answer),
    ]


def test_verlauf_fasst_werkzeugrunden_je_antwort_zusammen():
    messages = _exchange(
        "Was ist -F2?", "-F2 ist ein Motorschutzschalter [[01_Stromlaufplan_FB-01.pdf|/3.2]].", REFS
    ) + _exchange("Und -K1?", "-K1 ist das Hauptschuetz.", [REFS[0], REFS[0]])
    history = _history(messages)
    assert [m.role for m in history] == ["user", "assistant", "user", "assistant"]
    assert history[0].content == "Was ist -F2?" and history[1].content.startswith(
        "-F2 ist ein Motorschutzschalter"
    )
    assert [c.name for c in history[1].tool_calls] == ["find_tag"] and history[1].tool_calls[
        0
    ].args == {"tag": "-F2"}
    assert [s.filename for s in history[1].sources] == [
        "01_Stromlaufplan_FB-01.pdf",
        "02_Stueckliste_FB-01.xlsx",
    ]
    assert [s.filename for s in history[3].sources] == [
        "01_Stromlaufplan_FB-01.pdf"
    ]  # dedupliziert
    assert (
        history[1].meta is None
    )  # meta kommt erst aus build_meta (Datenbank), nicht aus dem Verlauf


def test_verlauf_ohne_werkzeuge_und_mit_blockinhalt():
    messages = [
        HumanMessage("Hallo"),
        AIMessage(
            content=[{"type": "text", "text": "Hallo "}, {"type": "text", "text": "zurueck"}]
        ),
    ]
    [user, assistant] = _history(messages)
    assert (user.content, assistant.content, assistant.sources, assistant.tool_calls) == (
        "Hallo",
        "Hallo zurueck",
        [],
        [],
    )
