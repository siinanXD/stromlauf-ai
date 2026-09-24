import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session, session_scope
from app.models import Conversation
from app.schemas import ChatRequest, ConversationOut, MessageOut, SourceRef, ToolCallOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


def _text_of(content) -> str:
    """Anthropic liefert Content als String oder Blockliste (text, thinking, tool_use...)."""
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _dedupe_sources(refs: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for ref in refs:
        key = (ref.get("document_id"), ref.get("page"), ref.get("section") if not ref.get("page") else "")
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


def _thread_config(conversation_id: str, source_ids: list[str]) -> dict:
    return {
        "configurable": {"thread_id": conversation_id, "source_ids": source_ids},
        "recursion_limit": 60,
    }


async def _close_dangling_tool_calls(graph, config: dict) -> None:
    """Nach einem abgebrochenen Stream kann ein tool_use ohne tool_result im Verlauf stehen;
    die Anthropic-API lehnt das ab. Fehlende Ergebnisse als abgebrochen nachtragen."""
    state = await graph.aget_state(config)
    messages = state.values.get("messages", [])
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.tool_calls:
            missing = [c for c in message.tool_calls if c["id"] not in answered]
            if missing:
                await graph.aupdate_state(
                    config,
                    {
                        "messages": [
                            ToolMessage("Abgebrochen (keine Antwort).", tool_call_id=c["id"])
                            for c in missing
                        ]
                    },
                    as_node="tools",
                )
            return


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(session: Session = Depends(get_session)):
    return session.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all()


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str, request: Request, session: Session = Depends(get_session)
):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Chat nicht gefunden")
    session.delete(conversation)
    session.commit()
    await request.app.state.checkpointer.adelete_thread(conversation_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(conversation_id: str, request: Request):
    graph = request.app.state.graph
    state = await graph.aget_state(_thread_config(conversation_id, []))
    result: list[MessageOut] = []
    current: MessageOut | None = None
    refs: list[dict] = []

    def flush():
        nonlocal current, refs
        if current is not None:
            current.sources = [SourceRef(**r) for r in _dedupe_sources(refs)]
            result.append(current)
        current, refs = None, []

    for message in state.values.get("messages", []):
        if isinstance(message, HumanMessage):
            flush()
            result.append(MessageOut(role="user", content=_text_of(message.content)))
        elif isinstance(message, AIMessage):
            current = current or MessageOut(role="assistant", content="")
            text = _text_of(message.content)
            if text:
                current.content = f"{current.content}\n\n{text}".strip()
            current.tool_calls += [
                ToolCallOut(name=c["name"], args=c["args"]) for c in message.tool_calls
            ]
        elif isinstance(message, ToolMessage) and isinstance(message.artifact, list):
            refs += message.artifact
    flush()
    return result


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    if not get_settings().anthropic_api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY fehlt. In .env eintragen und Backend neu starten.")
    graph = request.app.state.graph

    with session_scope() as session:
        conversation = session.get(Conversation, body.conversation_id) if body.conversation_id else None
        if conversation is None:
            title = " ".join(body.message.split())
            conversation = Conversation(title=title[:80] + ("…" if len(title) > 80 else ""))
            session.add(conversation)
        conversation.source_ids = body.source_ids
        conversation.updated_at = datetime.now(timezone.utc)
        session.flush()
        conversation_id, title = conversation.id, conversation.title

    config = _thread_config(conversation_id, body.source_ids)

    async def stream() -> AsyncIterator[str]:
        yield _sse("conversation", {"id": conversation_id, "title": title})
        refs: list[dict] = []
        try:
            await _close_dangling_tool_calls(graph, config)
            async for mode, payload in graph.astream(
                {"messages": [HumanMessage(body.message)]},
                config,
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    chunk, meta = payload
                    if isinstance(chunk, AIMessageChunk) and meta.get("langgraph_node") == "agent":
                        text = _text_of(chunk.content)
                        if text:
                            yield _sse("token", {"text": text})
                    continue
                for update in payload.values():
                    for message in (update or {}).get("messages", []):
                        if isinstance(message, AIMessage):
                            for call in message.tool_calls:
                                yield _sse("tool_start", {"name": call["name"], "args": call["args"]})
                            if message.tool_calls:
                                yield _sse("token", {"text": "\n\n"})
                            if message.response_metadata.get("stop_reason") == "refusal":
                                yield _sse("error", {"message": "Das Modell hat die Anfrage abgelehnt."})
                        elif isinstance(message, ToolMessage):
                            yield _sse("tool_end", {"name": message.name})
                            if isinstance(message.artifact, list):
                                refs += message.artifact
                                yield _sse("sources", _dedupe_sources(refs))
            yield _sse("done", {})
        except Exception as exc:
            logger.exception("Chat fehlgeschlagen")
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
