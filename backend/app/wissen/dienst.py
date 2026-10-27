"""Gelerntes Wissen: Notizen speichern, Lern-Aufruf ans Modell, Obsidian-Datei schreiben."""

import logging
import os
import threading
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger
from app.config import get_settings
from app.db import session_scope
from app.llm import make_chat_model
from app.models import Document, Machine, MachineNote
from app.schemas import BelegOut, NoteOut
from app.tenancy import reset_workspace, set_workspace
from app.tracing import trace_config
from app.wissen.lernen import (
    MAX_CHAT,
    MAX_PROMPT,
    belege_nummerieren,
    lern_prompt,
    normalisiert,
    ohne_dubletten,
    parse_saetze,
)
from app.wissen.obsidian import dateiname, markdown

logger = logging.getLogger(__name__)

_sperren: defaultdict[Path, threading.Lock] = defaultdict(threading.Lock)
_sperren_zugriff = threading.Lock()


def _dateinamen(session: Session, notes: list[MachineNote]) -> dict[str, str]:
    """Dateiname je `document_id` aller Belege; fehlende Dokumente fehlen im Ergebnis."""
    ids = {b["document_id"] for note in notes for b in note.belege}
    if not ids:
        return {}
    rows = session.execute(select(Document.id, Document.filename).where(Document.id.in_(ids)))
    return {document_id: filename for document_id, filename in rows}


def _out(note: MachineNote, dateinamen: dict[str, str]) -> NoteOut:
    return NoteOut(
        id=note.id,
        machine_id=note.machine_id,
        text=note.text,
        quelle=note.quelle,
        belege=[
            BelegOut(
                document_id=b["document_id"],
                page=b.get("page"),
                filename=dateinamen.get(b["document_id"], ""),
            )
            for b in note.belege
        ],
        gesperrt=note.gesperrt,
        run_id=note.run_id,
        conversation_id=note.conversation_id,
        created_at=note.created_at,
    )


def note_out(session: Session, note: MachineNote) -> NoteOut:
    return _out(note, _dateinamen(session, [note]))


def notizen_ausgeben(session: Session, notes: list[MachineNote]) -> list[NoteOut]:
    dateinamen = _dateinamen(session, notes)
    return [_out(note, dateinamen) for note in notes]


def notizen_fuer(
    session: Session, machine_id: str, limit: int | None = MAX_PROMPT
) -> list[MachineNote]:
    """Gesperrte zuerst, dann neueste zuerst; `limit=None` liefert alle."""
    stmt = (
        select(MachineNote)
        .where(MachineNote.machine_id == machine_id)
        .order_by(MachineNote.gesperrt.desc(), MachineNote.created_at.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def schreibe_obsidian(session: Session, machine: Machine) -> Path:
    """Markdown-Datei der Maschine atomar neu schreiben; nach dem Commit aufrufen.

    Reihenfolge: gesperrte zuerst, dann älteste zuerst.
    """
    notes = list(
        session.scalars(
            select(MachineNote)
            .where(MachineNote.machine_id == machine.id)
            .order_by(MachineNote.gesperrt.desc(), MachineNote.created_at.asc())
        )
    )
    dateinamen = _dateinamen(session, notes)
    eintraege = [
        {
            "text": n.text,
            "quelle": n.quelle,
            "gesperrt": n.gesperrt,
            "belege": [
                {"filename": dateinamen.get(b["document_id"], ""), "page": b.get("page")}
                for b in n.belege
            ],
        }
        for n in notes
    ]
    pfad = get_settings().data_dir / "wissen" / f"{dateiname(machine.name, machine.id)}.md"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    stand = datetime.now(UTC).isoformat()
    inhalt = markdown(machine.id, machine.name, stand, eintraege)
    with _sperren_zugriff:
        sperre = _sperren[pfad]
    with sperre:  # ein Schreiber je Datei; der Inhalt wird erst unter der Sperre gelesen
        temp = pfad.with_name(f"{pfad.name}.{threading.get_ident()}.tmp")
        temp.write_text(inhalt, encoding="utf-8")
        os.replace(temp, pfad)
    return pfad


def speichere(
    session: Session,
    machine: Machine,
    saetze: list[dict],
    *,
    quelle: str,
    run_id: str | None = None,
    conversation_id: str | None = None,
) -> int:
    """Neue Sätze (ohne Dubletten) ablegen; Anzahl neu. Die Datei schreibt der Aufrufer nach dem Commit."""
    vorhanden = [normalisiert(n.text) for n in notizen_fuer(session, machine.id, limit=None)]
    neu = ohne_dubletten(saetze, vorhanden)
    for satz in neu:
        session.add(
            MachineNote(
                machine_id=machine.id,
                text=satz["text"],
                quelle=quelle,
                belege=satz["belege"],
                run_id=run_id,
                conversation_id=conversation_id,
            )
        )
    session.flush()
    return len(neu)


def frage_modell(
    model: str, prompt: str, *, machine_id: str, session_id: str, tags: list[str]
) -> str:
    """Ein Modellaufruf ohne Werkzeuge; Kosten kommen mit Zweck `wissen.lernen` ins Kostenbuch."""
    from app.api.chat import _text_of  # lazy: app.api.chat importiert dieses Modul (kein Zyklus)

    config, collector = ledger.collect(trace_config(session_id, ["wissen", *tags], model), model)
    antwort = make_chat_model(model, max_tokens=1500, max_retries=2).invoke(
        [HumanMessage(prompt)], config
    )
    with session_scope() as session:
        ledger.record_usage(
            session, collector.total(), purpose="wissen.lernen", machine_id=machine_id
        )
    return _text_of(antwort.content)


def lerne(
    machine_id: str,
    model: str,
    kontext: str,
    antworten: list[dict],
    *,
    max_saetze: int,
    quelle: str,
    run_id: str | None = None,
    conversation_id: str | None = None,
    session_id: str,
) -> int:
    """Aus Antworten belegte Sätze lernen; wirft bei Modellfehlern, der Aufrufer entscheidet."""
    with session_scope() as session:
        machine = session.get(Machine, machine_id)
        if machine is None or machine.source_id is None:
            return 0
        erlaubt = set(
            session.scalars(select(Document.id).where(Document.source_id == machine.source_id))
        )
    belege = belege_nummerieren(antworten, erlaubt)
    if not belege:
        return 0
    prompt = lern_prompt(kontext, antworten, belege, max_saetze)
    text = frage_modell(model, prompt, machine_id=machine_id, session_id=session_id, tags=[quelle])
    saetze = parse_saetze(text, belege, max_saetze)
    with session_scope() as session:
        machine = session.get(Machine, machine_id)
        neu = speichere(
            session, machine, saetze, quelle=quelle, run_id=run_id, conversation_id=conversation_id
        )
    with session_scope() as session:  # erst nach dem Commit: Datei zeigt nur Festgeschriebenes
        schreibe_obsidian(session, session.get(Machine, machine_id))
    return neu


def lerne_aus_chat(
    machine_id: str,
    workspace_id: str | None,
    model: str,
    frage: str,
    antwort: str,
    refs: list[dict],
    conversation_id: str,
) -> None:
    """Nach einer Chat-Antwort lernen; wirft nie."""
    if get_settings().demo_mode:
        return
    token = set_workspace(workspace_id)
    try:
        with session_scope() as session:
            machine = session.get(Machine, machine_id)
            name = machine.name if machine else None
        if name is None:
            return
        lerne(
            machine_id,
            model,
            f"Maschine {name}",
            [{"question": frage, "answer_md": antwort, "sources": refs}],
            max_saetze=MAX_CHAT,
            quelle="chat",
            conversation_id=conversation_id,
            session_id=conversation_id,
        )
    except Exception:
        logger.exception("Lernen nach dem Chat fehlgeschlagen (Maschine %s)", machine_id)
    finally:
        reset_workspace(token)
