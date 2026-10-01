import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import ledger
from app.agent.prompts import PROMPT_VERSION
from app.api.answer_meta import build_meta, known_device_tags, tags_in_answer
from app.citations import check_answer
from app.config import get_settings
from app.db import get_session, session_scope
from app.llm import PROVIDER_ENV, api_key_for, split_model
from app.models import Conversation, KnowledgeSource, Machine
from app.schemas import (
    ChatRequest,
    CitationValidateOut,
    CitationValidateRequest,
    ConversationOut,
    ConversationPatch,
    MessageOut,
    SourceRef,
    ToolCallOut,
)
from app.tenancy import current_workspace_id, reset_workspace, same_workspace, set_workspace
from app.tracing import trace_config

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
        key = (
            ref.get("document_id"),
            ref.get("page"),
            ref.get("section") if not ref.get("page") else "",
        )
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


def _thread_config(
    conversation_id: str,
    source_ids: list[str],
    machine: dict | None = None,
    model: str | None = None,
) -> dict:
    configurable = {"thread_id": conversation_id, "source_ids": source_ids}
    if machine:
        configurable["machine"] = machine
    if model:
        configurable["model"] = model
    return {"configurable": configurable, "recursion_limit": 60}


def effective_model(requested: str | None) -> str:
    """Modell dieser Anfrage: Wunsch aus dem Body (Evals) oder CHAT_MODEL; 400 bei unbekanntem Namen oder fehlendem Schluessel."""
    settings = get_settings()
    name = (requested or "").strip() or settings.chat_model
    try:
        provider, _ = split_model(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not api_key_for(provider, settings):
        raise HTTPException(
            400,
            f"{PROVIDER_ENV[provider]} fehlt fuer Modell {name!r}. In .env eintragen und Backend neu starten.",
        )
    return name


def machine_scope(session: Session, machine_id: str) -> tuple[list[str], dict]:
    """Fester Scope eines Maschinen-Chats: nur die Wissensquelle der Maschine."""
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    if not machine.source_id:
        raise HTTPException(409, "Maschine hat keine Wissensquelle; im Tab Dokumente eine waehlen")
    context = {
        "id": machine.id,
        "name": machine.name,
        "hall": machine.hall.name if machine.hall else "",
    }
    return [machine.source_id], context


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
def list_conversations(
    source_id: str | None = None,
    machine_id: str | None = None,
    session: Session = Depends(get_session),
):
    """Alle Chats; mit source_id nur die, deren Scope genau diese Quelle ist (Maschinen-Chat).

    machine_id liefert dasselbe wie source_id mit der Quelle der Maschine: die Stoerfaelle der Maschinenseite kommen
    so in einem Abruf, ohne erst die Maschine zu laden."""
    if source_id is not None and machine_id is not None:
        raise HTTPException(422, "Entweder source_id oder machine_id angeben, nicht beides")
    if machine_id is not None:
        machine = session.get(Machine, machine_id)
        if machine is None or not same_workspace(machine):
            raise HTTPException(404, "Maschine nicht gefunden")
        if not machine.source_id:
            raise HTTPException(404, "Maschine hat keine Wissensquelle und damit keine Stoerfaelle")
        source_id = machine.source_id
    rows = session.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all()
    if source_id:
        rows = [c for c in rows if list(c.source_ids or []) == [source_id]]
    return rows


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: str, body: ConversationPatch, session: Session = Depends(get_session)
):
    """Stoerfall abschliessen (outcome resolved, optional mit Befund) oder wieder oeffnen."""
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or not same_workspace(conversation):
        raise HTTPException(404, "Chat nicht gefunden")
    for key, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(conversation, key, value)
    session.commit()
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str, request: Request, session: Session = Depends(get_session)
):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or not same_workspace(conversation):
        raise HTTPException(404, "Chat nicht gefunden")
    session.delete(conversation)
    session.commit()
    await request.app.state.checkpointer.adelete_thread(conversation_id)


def _history(messages: list) -> list[MessageOut]:
    """LangGraph-Verlauf -> Nachrichten: je Frage eine Antwort mit allen Werkzeugrunden und Fundstellen."""
    result: list[MessageOut] = []
    current: MessageOut | None = None
    refs: list[dict] = []

    def flush():
        nonlocal current, refs
        if current is not None:
            current.sources = [SourceRef(**r) for r in _dedupe_sources(refs)]
            result.append(current)
        current, refs = None, []

    for message in messages:
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


def _history_meta(
    history: list[MessageOut], source_ids: list[str], machine_id: str | None
) -> list[dict | None]:
    """meta je Antwort nachrechnen (Issue #47): dieselbe Funktion wie am Ende des Streams, eine Session fuer alle."""
    with session_scope() as meta_session:
        return [
            build_meta(
                meta_session,
                answer=message.content,
                citations=[s.model_dump() for s in message.sources],
                source_ids=source_ids,
                machine_id=machine_id,
            )
            if message.role == "assistant"
            else None
            for message in history
        ]


MESSAGE_PAGE_MAX = 200


def message_page(
    history: list[MessageOut], limit: int | None, before: int | None
) -> list[MessageOut]:
    """Nachrichten mit ihrer Position im ganzen Verlauf (index). before ist exklusiv, limit nimmt die letzten
    Nachrichten davor, in zeitlicher Reihenfolge; ohne beide kommt der ganze Verlauf."""
    for index, message in enumerate(history):
        message.index = index
    end = len(history) if before is None else max(0, min(before, len(history)))
    start = 0 if limit is None else max(0, end - limit)
    return history[start:end]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: str,
    request: Request,
    machine_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=MESSAGE_PAGE_MAX),
    before: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
):
    """Verlauf eines Chats. Jede Antwort traegt ihr meta (Bauteile, Belege, geprueft Zitate) wie im Live-Stream,
    deterministisch nachgerechnet und ohne Modellaufruf; machine_id liefert die Schaltschrank-Belege der Maschine
    (ohne Angabe: die Maschine der einzigen Quelle des Chats). limit und before liefern ein Stueck des Verlaufs
    (message_page); meta wird nur fuer dieses Stueck gerechnet."""
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or not same_workspace(conversation):
        raise HTTPException(404, "Chat nicht gefunden")
    if machine_id is not None:
        machine = session.get(Machine, machine_id)
        if machine is None or not same_workspace(machine):
            raise HTTPException(404, "Maschine nicht gefunden")
    source_ids = list(conversation.source_ids or [])
    if machine_id is None and len(source_ids) == 1:
        machine_id = ledger.machine_for_source(session, source_ids[0])
    graph = request.app.state.graph
    state = await graph.aget_state(_thread_config(conversation_id, []))
    history = message_page(_history(state.values.get("messages", [])), limit, before)
    # Im Threadpool: der Zitat-Resolver schlaegt Blaetter per pdfium (globaler Lock) nach
    metas = await run_in_threadpool(_history_meta, history, source_ids, machine_id)
    for message, meta in zip(history, metas, strict=True):
        message.meta = meta
    return history


async def agent_events(
    graph,
    config: dict,
    message: str,
    *,
    model: str,
    machine_id: str | None,
    max_tool_calls: int,
    timeout_s: float,
) -> AsyncIterator[tuple[str, dict | list]]:
    """Ereignisse einer Agentenantwort: token, usage, tool_start, tool_end, sources, error.

    Leitplanken (Issue #48): nach `max_tool_calls` Werkzeugaufrufen und nach `timeout_s` Sekunden endet die
    Antwort mit einem error-Ereignis statt weiterzulaufen; ein abgebrochener Werkzeugaufruf wird beim naechsten
    Chat von _close_dangling_tool_calls nachgetragen. Jede Modellantwort wird der Maschine zugebucht.
    """
    refs: list[dict] = []
    calls = 0
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    stream = graph.astream(
        {"messages": [HumanMessage(message)]}, config, stream_mode=["messages", "updates"]
    ).__aiter__()
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError
            try:
                # Zeitlimit nur um das Warten auf den Agenten: ein Abbruch trifft nie das Senden an den Client
                mode, payload = await asyncio.wait_for(stream.__anext__(), timeout=remaining)
            except StopAsyncIteration:
                break
            if mode == "messages":
                chunk, meta = payload
                if isinstance(chunk, AIMessageChunk) and meta.get("langgraph_node") == "agent":
                    text = _text_of(chunk.content)
                    if text:
                        yield "token", {"text": text}
                continue
            for update in payload.values():
                for item in (update or {}).get("messages", []):
                    if isinstance(item, AIMessage):
                        usage = ledger.usage_of(item, model)
                        if usage is not None:
                            # jede Modellantwort (auch Werkzeugrunden) wird der Maschine zugebucht
                            with session_scope() as booking:
                                call = ledger.record_usage(
                                    booking, usage, purpose="chat", machine_id=machine_id
                                )
                                cost_cents = call.cost_microcents / ledger.MICROCENTS_PER_CENT
                            yield (
                                "usage",
                                {
                                    "input_tokens": usage.input_tokens,
                                    "output_tokens": usage.output_tokens,
                                    "cache_read_tokens": usage.cache_read_tokens,
                                    "cache_creation_tokens": usage.cache_creation_tokens,
                                    "model": usage.model,
                                    "cost_cents": cost_cents,
                                },
                            )
                        if item.tool_calls:
                            calls += len(item.tool_calls)
                            if calls > max_tool_calls:
                                yield (
                                    "error",
                                    {
                                        "message": f"Abgebrochen: mehr als {max_tool_calls} "
                                        "Werkzeugaufrufe in einer Antwort."
                                    },
                                )
                                return
                            for call in item.tool_calls:
                                yield "tool_start", {"name": call["name"], "args": call["args"]}
                            yield "token", {"text": "\n\n"}
                        if item.response_metadata.get("stop_reason") == "refusal":
                            yield "error", {"message": "Das Modell hat die Anfrage abgelehnt."}
                    elif isinstance(item, ToolMessage):
                        yield "tool_end", {"name": item.name}
                        if isinstance(item.artifact, list):
                            refs += item.artifact
                            yield "sources", _dedupe_sources(refs)
    except TimeoutError:
        yield "error", {"message": f"Abgebrochen: Zeitlimit von {timeout_s:g} s ueberschritten."}
    finally:
        await stream.aclose()


def _meta_for(
    answer: str, citations: list[dict], source_ids: list[str], machine_id: str | None
) -> dict:
    with session_scope() as meta_session:
        return build_meta(
            meta_session,
            answer=answer,
            citations=citations,
            source_ids=source_ids,
            machine_id=machine_id,
        )


@router.post("/answers/validate-citations", response_model=CitationValidateOut)
def validate_citations(body: CitationValidateRequest, session: Session = Depends(get_session)):
    """Belege einer (gespeicherten) Antwort deterministisch pruefen, ohne Modellaufruf (Issue #46)."""
    visible = set(
        session.scalars(select(KnowledgeSource.id).where(KnowledgeSource.id.in_(body.source_ids)))
    )
    if visible != set(body.source_ids):
        raise HTTPException(404, "Wissensquelle nicht gefunden")
    refs = [s.model_dump() for s in body.sources] if body.sources is not None else None
    checks, valid = check_answer(session, body.answer, body.source_ids, refs)
    referenced = tags_in_answer(body.answer, known_device_tags(session, body.source_ids))
    return {"citation_checks": checks, "citations_valid": valid, "referenced_tags": referenced}


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    model = effective_model(body.model)
    graph = request.app.state.graph

    workspace_id = current_workspace_id()
    with session_scope() as session:
        source_ids, machine = body.source_ids, None
        if body.machine_id:
            source_ids, machine = machine_scope(session, body.machine_id)
        elif source_ids:
            # Nur Quellen des eigenen Workspace duerfen in den Scope
            visible = set(
                session.scalars(
                    select(KnowledgeSource.id).where(KnowledgeSource.id.in_(source_ids))
                )
            )
            if visible != set(source_ids):
                raise HTTPException(404, "Wissensquelle nicht gefunden")
        # Monatslimit des Workspace: Ablehnung, bevor der Provider gerufen wird (402 via BudgetExceeded)
        ledger.check_budget(session)
        conversation = (
            session.get(Conversation, body.conversation_id) if body.conversation_id else None
        )
        if conversation is not None and not same_workspace(conversation):
            raise HTTPException(404, "Chat nicht gefunden")
        if conversation is None:
            title = " ".join(body.message.split())
            conversation = Conversation(title=title[:80] + ("…" if len(title) > 80 else ""))
            session.add(conversation)
        conversation.source_ids = source_ids
        conversation.updated_at = datetime.now(timezone.utc)
        session.flush()
        conversation_id, title = conversation.id, conversation.title

    config = _thread_config(conversation_id, source_ids, machine, model)
    config.update(
        trace_config(conversation_id, [*body.trace_tags, f"prompt:v{PROMPT_VERSION}"], model)
    )
    settings = get_settings()

    async def stream() -> AsyncIterator[str]:
        yield _sse("conversation", {"id": conversation_id, "title": title})
        refs: list[dict] = []
        answer_parts: list[str] = []
        # Der Stream laeuft nach der Middleware weiter: Workspace fuer die Agenten-Werkzeuge erneut setzen
        workspace_token = set_workspace(workspace_id)
        try:
            await _close_dangling_tool_calls(graph, config)
            async for event, data in agent_events(
                graph,
                config,
                body.message,
                model=model,
                machine_id=body.machine_id,
                max_tool_calls=settings.chat_max_tool_calls,
                timeout_s=settings.chat_timeout_s,
            ):
                if event == "token":
                    answer_parts.append(data["text"])
                elif event == "sources":
                    refs = list(data)
                yield _sse(event, data)
            # Antwort-Vertrag (MB-4): referenzierte Bauteile, Zitate, Belege - deterministisch aus Index und Fundstellen.
            # Im Threadpool, weil der Zitat-Resolver Blaetter per pdfium (globaler Lock) nachschlaegt und der
            # Event-Loop sonst fuer alle Mandanten steht.
            meta = await run_in_threadpool(
                _meta_for, "".join(answer_parts), refs, source_ids, body.machine_id
            )
            yield _sse("meta", meta)
            yield _sse("done", {})
        except Exception as exc:
            logger.exception("Chat fehlgeschlagen")
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
        finally:
            reset_workspace(workspace_token)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
