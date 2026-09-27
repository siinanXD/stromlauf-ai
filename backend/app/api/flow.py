"""Ablauf einer Maschine (Schrittkette) als JSON fuer die Animation; Extraktion auf Wunsch.

GET liest nur den Cache (kein Modell, keine Kosten). POST extrahiert mit den Dokumenten der
Wissensquelle (kostet Tokens, einmal je Dokumentstand) und fuellt damit den Cache.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.flow import extract
from app.flow.sources import DocText, load_document
from app.models import DocStatus, DocType, Document, Machine
from app.tenancy import same_workspace

router = APIRouter(prefix="/api", tags=["flow"])

# Nur Dokumente, aus denen Schrittkette und I/O hervorgehen; Stromlaufplaene bringen fuer Text wenig
FLOW_DOC_TYPES = (DocType.MANUAL, DocType.PLC_PROGRAM, DocType.PLC_SYMBOLS, DocType.BOM, DocType.TERMINAL_PLAN, DocType.OTHER)


def flow_documents(documents: list[Document]) -> list[Document]:
    """Fertige Dokumente der Quelle in fester Reihenfolge (Typ, Name), damit der Cache-Schluessel stabil ist."""
    order = {t: i for i, t in enumerate(FLOW_DOC_TYPES)}
    chosen = [d for d in documents if d.status == DocStatus.READY and d.doc_type in order]
    return sorted(chosen, key=lambda d: (order[d.doc_type], d.filename))


def _machine_docs(session: Session, machine_id: str) -> tuple[Machine, list[DocText], list[Path]]:
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    if not machine.source_id:
        raise HTTPException(409, "Maschine hat keine Wissensquelle")
    documents = flow_documents(
        session.scalars(select(Document).where(Document.source_id == machine.source_id)).all()
    )
    if not documents:
        raise HTTPException(409, "Wissensquelle hat kein fertig verarbeitetes Handbuch, AWL oder Symboltabelle")
    paths = [Path(d.storage_path) for d in documents]
    missing = [d.filename for d, p in zip(documents, paths, strict=True) if not p.exists()]
    if missing:
        raise HTTPException(409, f"Dateien fehlen auf der Platte: {', '.join(missing)}")
    docs = [load_document(p, d.doc_type, name=d.filename) for d, p in zip(documents, paths, strict=True)]
    return machine, docs, paths


@router.get("/machines/{machine_id}/flow")
def get_flow(machine_id: str, session: Session = Depends(get_session)) -> dict:
    """Ablauf-JSON aus dem Cache; 404 mit Hinweis, wenn noch nicht extrahiert."""
    _, docs, _ = _machine_docs(session, machine_id)
    key = extract.cache_key(docs)
    target = extract.cache_path(key)
    if not target.exists():
        raise HTTPException(
            404,
            "Noch kein Ablauf extrahiert. POST /api/machines/{id}/flow/extract (kostet Tokens) oder "
            f"scripts/extract_flow.py mit denselben Dateien; Cache-Schluessel {key[:12]}…",
        )
    flow = extract.schema.MachineFlow.model_validate_json(target.read_text(encoding="utf-8"))
    flow.meta.cached = True
    return flow.model_dump(mode="json")


@router.post("/machines/{machine_id}/flow/extract")
def extract_machine_flow(machine_id: str, force: bool = False, session: Session = Depends(get_session)) -> dict:
    """Extraktion anstossen (synchron, Budget 30 s). Gleicher Dokumentstand kommt aus dem Cache."""
    machine, docs, paths = _machine_docs(session, machine_id)
    names = {p: d.file for p, d in zip(paths, docs, strict=True)}
    try:
        flow = extract.extract_flow(paths, machine=machine.name, force=force, names=names)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return flow.model_dump(mode="json")
