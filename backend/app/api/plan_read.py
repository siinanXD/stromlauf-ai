"""Planlesen per Modell je Wissensquelle (Spec 4.2): Schaetzung, Lauf auf Knopfdruck, Status.

- POST /api/sources/{source_id}/plan-read?dry_run=true|false liefert
  {model, pages, estimate_usd, edges, dropped, cost_usd}. Ohne Angabe gilt dry_run=true: nur Seitenzahl und
  Schaetzung, kein Modellaufruf. dry_run=false liest alle Stromlaufplan-PDFs der Quelle und kostet Geld (ausser
  bei lokalem Endpunkt). 409, wenn PLAN_READER_MODEL leer ist; 400 mit dem Namen der Variable, wenn der
  Schluessel des Anbieters fehlt.
- GET /api/sources/{source_id}/plan-read liefert {configured, model, cached, edges, dropped, cost_usd}.

Gespeichert wird je Datei ueber `plan_edges.write_model_edges`; der Signalweg liest die Kanten mit via "modell".
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger
from app.config import get_settings
from app.db import get_session
from app.ingestion.plan_edges import read_model_edges, read_model_meta, write_model_edges
from app.ingestion.plan_model import (
    LENGTH_LIMIT,
    PAGE_TAG_TYPES,
    PROMPT_VERSION,
    estimate_usd,
    make_model,
    pages_to_read,
    read_pages,
    run_cost_usd,
    total_usage,
)
from app.llm import MissingKeyError
from app.models import DocStatus, DocType, Document, KnowledgeSource, TagOccurrence
from app.tenancy import same_workspace
from app.tracing import trace_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["plan-read"])

NO_MODEL = {"reason": "no_model", "message": "Kein Modell eingerichtet"}


class PlanReadOut(BaseModel):
    model: str
    pages: int
    estimate_usd: float
    edges: int | None = None
    dropped: int | None = None
    cost_usd: float | None = None


class PlanReadStatusOut(BaseModel):
    configured: bool
    model: str
    cached: bool
    edges: int
    dropped: int
    cost_usd: float | None = None


def _get_source(session: Session, source_id: str) -> KnowledgeSource:
    source = session.get(KnowledgeSource, source_id)
    if source is None or not same_workspace(source):
        raise HTTPException(404, "Wissensquelle nicht gefunden")
    return source


def schematic_pdfs(session: Session, source_id: str) -> list[Document]:
    """Fertig gelesene Stromlaufplaene der Quelle als PDF, deren Datei noch da ist."""
    documents = session.scalars(
        select(Document)
        .where(
            Document.source_id == source_id,
            Document.doc_type == DocType.SCHEMATIC,
            Document.status == DocStatus.READY,
        )
        .order_by(Document.filename)
    ).all()
    return [
        d
        for d in documents
        if Path(d.storage_path).suffix.lower() == ".pdf" and Path(d.storage_path).exists()
    ]


def page_tags(session: Session, document_id: str) -> dict[int, set[str]]:
    """Kennzeichen je Seite aus dem Index, nur moegliche Leitungsenden (keine Querverweise)."""
    rows = session.execute(
        select(TagOccurrence.page, TagOccurrence.tag).where(
            TagOccurrence.document_id == document_id,
            TagOccurrence.page.is_not(None),
            TagOccurrence.tag_type.in_(PAGE_TAG_TYPES),
        )
    ).all()
    tags: dict[int, set[str]] = {}
    for page, tag in rows:
        tags.setdefault(page, set()).add(tag)
    return tags


def _sum_costs(costs: list[float | None]) -> float | None:
    known = [cost for cost in costs if cost is not None]
    return round(sum(known), 6) if known else None


@router.get("/sources/{source_id}/plan-read", response_model=PlanReadStatusOut)
def plan_read_status(source_id: str, session: Session = Depends(get_session)):
    """Ist ein Modell eingerichtet, und liegt fuer alle Stromlaufplaene der Quelle schon ein Modelllauf vor?"""
    _get_source(session, source_id)
    settings = get_settings()
    documents = schematic_pdfs(session, source_id)
    metas = [(Path(d.storage_path), read_model_meta(Path(d.storage_path))) for d in documents]
    done = [(path, meta) for path, meta in metas if meta is not None]
    return PlanReadStatusOut(
        configured=bool(settings.plan_reader_model.strip()),
        model=settings.plan_reader_model.strip(),
        cached=bool(metas) and len(done) == len(metas),
        edges=sum(len(read_model_edges(path)) for path, _ in done),
        dropped=sum(int(meta.get("dropped") or 0) for _, meta in done),
        cost_usd=_sum_costs([meta.get("cost_usd") for _, meta in done]),
    )


@router.post("/sources/{source_id}/plan-read", response_model=PlanReadOut)
def plan_read(source_id: str, dry_run: bool = True, session: Session = Depends(get_session)):
    """Stromlaufplaene der Quelle per Modell lesen; mit dry_run nur Seitenzahl und Schaetzung."""
    _get_source(session, source_id)
    settings = get_settings()
    name = settings.plan_reader_model.strip()
    if not name:
        raise HTTPException(409, NO_MODEL)
    base_url = settings.plan_reader_base_url.strip()
    documents = schematic_pdfs(session, source_id)
    tags = {d.id: page_tags(session, d.id) for d in documents}
    pages = sum(len(pages_to_read(tags[d.id])) for d in documents)
    estimate = 0.0 if base_url else estimate_usd(name, pages)
    if dry_run:
        return PlanReadOut(model=name, pages=pages, estimate_usd=estimate)
    if pages == 0:
        return PlanReadOut(model=name, pages=0, estimate_usd=0.0, edges=0, dropped=0)

    try:
        model = make_model(name, base_url)
    except (
        MissingKeyError,
        ValueError,
    ) as exc:  # Konfiguration, kein Fehler des Anbieters (Issue #50)
        raise HTTPException(400, f"Planlesen nicht moeglich: {exc}") from exc
    if not base_url:  # ein lokaler Endpunkt kostet nichts und zaehlt nicht gegen das Monatslimit
        ledger.check_budget(session)

    edges = dropped = 0
    costs: list[float | None] = []
    errors: list[str] = []
    answered = 0
    for document in documents:
        path = Path(document.storage_path)
        if not pages_to_read(tags[document.id]):
            continue
        reads = read_pages(
            model,
            path,
            tags[document.id],
            model_name=name,
            trace=trace_config(document.id, ["ingestion", "planleser"], name),
            workers=settings.vision_concurrency,
        )
        failed = [read.page for read in reads if read.error]
        errors += [read.error for read in reads if read.error]
        cost = run_cost_usd(total_usage(reads), base_url)
        costs.append(cost)
        if len(failed) == len(reads):
            continue  # nichts gelesen: einen frueheren Lauf nicht mit einem leeren ueberschreiben
        answered += len(reads) - len(failed)
        kept = [edge for read in reads for edge in read.kept]
        lost = sum(len(read.dropped) for read in reads)
        meta = {
            "model": name,
            "pages": len(reads),
            "dropped": lost,
            "cost_usd": cost,
            "failed_pages": failed,
            "length_limit_pages": [read.page for read in reads if read.error == LENGTH_LIMIT],
            "local": bool(base_url),
            "prompt_version": PROMPT_VERSION,
        }
        write_model_edges(path, PROMPT_VERSION, kept, meta)
        edges += len(kept)
        dropped += lost
    if not answered:
        logger.error("Planlesen ohne eine gelesene Seite: %s", errors[:3])
        raise HTTPException(
            502, f"Planlesen fehlgeschlagen: {errors[0] if errors else 'keine Antwort'}"
        )
    return PlanReadOut(
        model=name,
        pages=pages,
        estimate_usd=estimate,
        edges=edges,
        dropped=dropped,
        cost_usd=_sum_costs(costs),
    )
