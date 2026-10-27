"""Orchestrator eines Ablaufs: Schritte 2 bis 8 nacheinander im Hintergrund-Thread.

Schritt 1 (hochladen) erledigt `POST /api/runs` und startet danach
`threading.Thread(target=starte_lauf, args=(run_id, graph, loop, hall_id), daemon=True)`. Jeder Schritt
schreibt seinen Zustand sofort in `runs.steps`; ein Fehler beendet den Lauf, nichts wirft.
Schritt 6 laeuft auf der Event-Loop von FastAPI, weil der Checkpointer des Graphen daran haengt.
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import func, select, text

from app import ledger
from app.ablauf.fragen import FRAGEN
from app.ablauf.schritte import abbrechen, beende, lauf_status, scheitere, starte
from app.ablauf.spur import Spur
from app.api.chat import _dedupe_sources, _text_of, machine_scope
from app.api.machine_map import machine_map_data
from app.api.onboarding import OnboardingRequest, onboard_machine, proposal_for
from app.api.sources import source_profile_data
from app.config import get_settings
from app.db import session_scope
from app.ingestion.pipeline import ingest_document
from app.models import Chunk, DocStatus, Document, Hall, KnowledgeSource, Machine, Run
from app.tenancy import require_workspace, reset_workspace, set_workspace
from app.tracing import trace_config
from app.wissen.dienst import lerne
from app.wissen.lernen import MAX_LAUF

logger = logging.getLogger(__name__)

HALLE = "Ablauf"
NEUSTART_FEHLER = "Backend neu gestartet"


@dataclass
class LaufKontext:
    run_id: str
    source_id: str
    workspace_id: str | None
    model: str
    graph: Any
    loop: asyncio.AbstractEventLoop | None
    machine_id: str | None = None
    hall_id: str | None = None
    machine: dict | None = None  # Kontext wie chat.machine_scope, fuer Schritt 6
    ergebnis: dict[str, Any] = field(default_factory=dict)  # je Schritt-Key -> steps[i]["result"]


def fehlertext(exc: BaseException, model: str) -> str:
    """Fehler als Satz fuer die Ablauf-Seite; nicht erreichbares Modell bekommt einen eigenen."""
    if isinstance(exc, ConnectionError | httpx.ConnectError) or "Connection" in type(exc).__name__:
        return f"Modell nicht erreichbar: {model}"
    if isinstance(exc, TimeoutError) and not str(exc):
        return "Zeitlimit überschritten"
    return f"{type(exc).__name__}: {exc}"


def _jetzt() -> str:
    return datetime.now(UTC).isoformat()


def brich_haengende_laeufe_ab(session) -> int:
    """Läufe, die ein Neustart mitten im Lauf erwischt hat, als gescheitert markieren (alle Workspaces).

    Ohne gesetzten Workspace filtert der ORM-Listener nicht (siehe app/tenancy.py).
    """
    laufende = session.scalars(select(Run).where(Run.status == "laeuft")).all()
    jetzt = datetime.now(UTC)
    for run in laufende:
        run.steps = abbrechen(list(run.steps), jetzt.isoformat(), NEUSTART_FEHLER)
        run.status, run.error, run.finished_at = "fehler", NEUSTART_FEHLER, jetzt
    return len(laufende)


def _speichere(run_id: str, aendere: Callable[[list[dict]], list[dict]], **felder) -> None:
    """Schritte aendern, Gesamtstatus nachziehen; am Ende des Laufs `finished_at` setzen."""
    with session_scope() as session:
        run = session.get(Run, run_id)
        run.steps = aendere(list(run.steps))
        run.status = lauf_status(run.steps)
        for name, wert in felder.items():
            setattr(run, name, wert)
        if run.status != "laeuft":
            run.finished_at = datetime.now(UTC)


def _mit_ergebnis(steps: list[dict], key: str, ergebnis: Any) -> list[dict]:
    return [{**s, "result": ergebnis} if s["key"] == key else s for s in steps]


# --- Schritte --------------------------------------------------------------------------------


def schritt_lesen(ctx: LaufKontext) -> str:
    """Jedes Dokument nacheinander einlesen; ein fehlgeschlagenes ist ein Schrittfehler."""
    with session_scope() as session:
        ids = list(
            session.scalars(
                select(Document.id)
                .where(Document.source_id == ctx.source_id)
                .order_by(Document.filename)
            )
        )
    if not ids:
        raise ValueError("Keine Dokumente in der Wissensquelle")
    for document_id in ids:
        ingest_document(document_id)
    with session_scope() as session:
        documents = session.scalars(select(Document).where(Document.id.in_(ids))).all()
        failed = [d for d in documents if d.status == DocStatus.FAILED]
        if failed:
            raise ValueError("; ".join(f"{d.filename}: {d.error}" for d in failed))
        chunks = session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.source_id == ctx.source_id)
        )
        pages = sum(d.page_count or 0 for d in documents)
        lines = [f"{d.filename}: {d.progress}" for d in documents]
    ctx.ergebnis["lesen"] = {"dokumente": len(ids)}
    return "\n".join([f"{len(ids)} Dokumente, {pages} Seiten, {chunks} Abschnitte", *lines])


def halle_sichern(session) -> Hall:
    """Halle „Ablauf“ des aktuellen Workspaces; legt sie an, falls sie fehlt.

    Der Advisory-Lock (gilt bis Commit) serialisiert parallele Anfragen, sonst entstuenden
    zwei Hallen gleichen Namens.
    """
    # Nur Postgres (pg_advisory_xact_lock, hashtext).
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"halle-ablauf:{require_workspace()}"},
    )
    hall = session.scalars(select(Hall).where(Hall.name == HALLE)).first()
    if hall is None:
        hall = Hall(name=HALLE, description="Maschinen aus dem Ablauf")
        session.add(hall)
        session.flush()
    return hall


def schritt_maschine(ctx: LaufKontext) -> str:
    """Vorschlag holen und die Maschine in der vorbereiteten Halle „Ablauf“ anlegen."""
    with session_scope() as session:
        source = session.get(KnowledgeSource, ctx.source_id)
        proposal = proposal_for(session, source)
        hall = (ctx.hall_id and session.get(Hall, ctx.hall_id)) or halle_sichern(session)
        request = OnboardingRequest(
            source_id=source.id,
            name=proposal.name,
            machine_type=proposal.machine_type,
            faults=proposal.faults,
        )
        machine = onboard_machine(session, hall, request)
        ctx.machine_id, ctx.hall_id = machine.id, hall.id
        return f"{machine.name} ({machine.machine_type}), {len(proposal.faults)} Störfälle"


def schritt_steckbrief(ctx: LaufKontext) -> str:
    with session_scope() as session:
        profile = source_profile_data(session, ctx.source_id)
    ctx.ergebnis["steckbrief"] = profile.model_dump(mode="json")
    present = sum(1 for t in profile.doc_types if t.present)
    return (
        f"{present} von {len(profile.doc_types)} Dokumenttypen, "
        f"{profile.summary.devices} Betriebsmittel, {profile.summary.gaps} Lücken"
    )


def schritt_modell(ctx: LaufKontext) -> str:
    with session_scope() as session:
        data = machine_map_data(session, session.get(Machine, ctx.machine_id))
    zones, parts = len(data["zones"]), data["part_count"]
    ctx.ergebnis["modell"] = {"zones": zones, "parts": parts}
    return f"{zones} Zonen, {parts} Bauteile"


def beantworte(graph, ctx: LaufKontext, frage: str, n: int) -> tuple[str, list[dict]]:
    """Eine Frage ueber den Agenten (eigener Thread je Frage), Kosten auf die Maschine buchen."""
    config = {
        "configurable": {
            "thread_id": f"run:{ctx.run_id}:{n}",
            "source_ids": [ctx.source_id],
            "machine": ctx.machine,
            "model": ctx.model,
        },
        "recursion_limit": 60,
    }
    tracing = trace_config(f"run:{ctx.run_id}", ["ablauf", "zusammenfassung"], ctx.model)
    config, collector = ledger.collect({**config, **tracing}, ctx.model)
    future = asyncio.run_coroutine_threadsafe(
        graph.ainvoke({"messages": [HumanMessage(frage)]}, config), ctx.loop
    )
    try:
        state = future.result(timeout=3 * get_settings().chat_timeout_s)
    except TimeoutError:
        future.cancel()
        raise
    with session_scope() as session:
        ledger.record_usage(
            session,
            collector.total(),
            purpose="ablauf.zusammenfassung",
            machine_id=ctx.machine_id,
        )
    messages = state["messages"]
    answer = next((_text_of(m.content) for m in reversed(messages) if isinstance(m, AIMessage)), "")
    refs = [
        ref
        for m in messages
        if isinstance(m, ToolMessage) and isinstance(m.artifact, list)
        for ref in m.artifact
    ]
    return answer, _dedupe_sources(refs)


def schritt_zusammenfassung(ctx: LaufKontext) -> str:
    with session_scope() as session:
        _, ctx.machine = machine_scope(session, ctx.machine_id)
    antworten = []
    for n, frage in enumerate(FRAGEN, start=1):
        start = time.perf_counter()
        answer, sources = beantworte(ctx.graph, ctx, frage, n)
        dauer_s = round(time.perf_counter() - start, 1)
        antworten.append(
            {"question": frage, "answer_md": answer, "sources": sources, "dauer_s": dauer_s}
        )
    ctx.ergebnis["zusammenfassung"] = antworten
    belege = sum(len(a["sources"]) for a in antworten)
    return f"{len(antworten)} Antworten, {belege} Belege"


def schritt_lernen(ctx: LaufKontext) -> str:
    """Aus den Antworten belegte Sätze für die Maschine lernen (ohne Beleg: 0 Sätze)."""
    profile = ctx.ergebnis.get("steckbrief") or {}
    kontext = json.dumps(
        {
            "maschine": ctx.machine["name"],
            "zusammenfassung": profile.get("summary"),
            "dokumente": [d["filename"] for d in profile.get("documents", [])],
        },
        ensure_ascii=False,
    )
    n = lerne(
        ctx.machine_id,
        ctx.model,
        kontext,
        ctx.ergebnis["zusammenfassung"],
        max_saetze=MAX_LAUF,
        quelle="lauf",
        run_id=ctx.run_id,
        session_id=f"run:{ctx.run_id}",
    )
    ctx.ergebnis["lernen"] = {"saetze": n}
    return "1 Satz gelernt" if n == 1 else f"{n} Sätze gelernt"


def schritt_fertig(ctx: LaufKontext) -> str:
    return f"/werk/maschine/{ctx.machine_id}"


# --- Ablauf ----------------------------------------------------------------------------------


def _fuehre_aus(ctx: LaufKontext, spur: Spur, key: str, schritt, eingabe: str) -> str | None:
    """Einen Schritt laufen lassen und speichern; None, wenn er gescheitert ist."""
    _speichere(ctx.run_id, lambda steps: starte(steps, key, _jetzt(), eingabe))
    try:
        with spur.schritt(key, eingabe) as span:
            ausgabe = schritt(ctx)
            span.output(ausgabe)
    except Exception as exc:  # noqa: BLE001 - jeder Fehler endet als Schrittfehler
        logger.exception("Ablauf %s: Schritt %s fehlgeschlagen", ctx.run_id, key)
        text = fehlertext(exc, ctx.model)
        _speichere(ctx.run_id, lambda steps: scheitere(steps, key, _jetzt(), text), error=text)
        return None

    def fertig(steps: list[dict]) -> list[dict]:
        steps = beende(steps, key, _jetzt(), ausgabe)
        return _mit_ergebnis(steps, key, ctx.ergebnis[key]) if key in ctx.ergebnis else steps

    _speichere(ctx.run_id, fertig, machine_id=ctx.machine_id)
    return ausgabe


def _markiere_abbruch(run_id: str, text: str) -> None:
    """Letzter Versuch, einen Lauf als gescheitert zu speichern, wenn das Speichern selbst brach."""
    try:
        with session_scope() as session:
            run = session.get(Run, run_id)
            run.status, run.error, run.finished_at = "fehler", text, datetime.now(UTC)
    except Exception:  # noqa: BLE001
        logger.exception("Ablauf %s: Abbruch nicht gespeichert", run_id)


def starte_lauf(
    run_id: str, graph, loop: asyncio.AbstractEventLoop | None, hall_id: str | None = None
) -> None:
    """Thread-Ziel: Schritte 2 bis 8 nacheinander. Wirft nie; Fehler stehen im Run."""
    try:
        with session_scope() as session:
            run = session.get(Run, run_id)
            if run is None:
                return
            ctx = LaufKontext(
                run.id, run.source_id, run.workspace_id, run.model, graph, loop, hall_id=hall_id
            )
            eingabe = next((s["output"] for s in run.steps if s["key"] == "hochladen"), "")
    except Exception:  # noqa: BLE001
        logger.exception("Ablauf %s nicht gestartet", run_id)
        return
    token = set_workspace(ctx.workspace_id)
    spur = Spur.fuer(run_id, ctx.model)
    status = "fehler"
    try:
        url = spur.url()
        if url:
            _speichere(run_id, lambda steps: steps, trace_url=url)
        schritte = [
            ("lesen", schritt_lesen),
            ("maschine", schritt_maschine),
            ("steckbrief", schritt_steckbrief),
            ("modell", schritt_modell),
            ("zusammenfassung", schritt_zusammenfassung),
            ("lernen", schritt_lernen),
            ("fertig", schritt_fertig),
        ]
        for key, schritt in schritte:
            eingabe = _fuehre_aus(ctx, spur, key, schritt, eingabe)
            if eingabe is None:
                return
        status = "fertig"
    except Exception as exc:  # noqa: BLE001 - etwa Datenbank weg beim Speichern
        logger.exception("Ablauf %s abgebrochen", run_id)
        _markiere_abbruch(run_id, fehlertext(exc, ctx.model))
    finally:
        spur.schliessen(status)
        reset_workspace(token)
