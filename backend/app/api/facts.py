"""Befundkarte fuer den Chat: was der Kennzeichen-Index zu einem Betriebsmittel weiss."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion.fact_card import build_fact_card, hits_of_single_source
from app.ingestion.tags import normalize_tag
from app.models import Chunk, Document, TagOccurrence
from app.schemas import FactCard

router = APIRouter(prefix="/api", tags=["facts"])

TABLE_DOC_TYPES = {"bom", "terminal_plan", "plc_symbols"}


@router.get("/facts", response_model=FactCard)
def fact_card(tag: str, source_ids: list[str] = Query(default=[]), session: Session = Depends(get_session)):
    normalized = normalize_tag(tag)
    statement = (
        select(TagOccurrence, Document)
        .join(Document, TagOccurrence.document_id == Document.id)
        .where(
            or_(
                TagOccurrence.tag == normalized,
                TagOccurrence.tag.like(f"{normalized}:%"),
                TagOccurrence.tag.like(f"%{normalized}"),
            )
        )
        .order_by(Document.doc_type, Document.filename, TagOccurrence.page, TagOccurrence.id)
        .limit(120)
    )
    if source_ids:
        statement = statement.where(TagOccurrence.source_id.in_(source_ids))
    hits = [
        {
            "source_id": occurrence.source_id,
            "doc_type": document.doc_type,
            "filename": document.filename,
            "document_id": document.id,
            "page": occurrence.page,
            "section": occurrence.section,
            "context": occurrence.context,
        }
        for occurrence, document in session.execute(statement).all()
    ]
    # Gleiches BMK in mehreren Anlagen (keine Quelle gewaehlt): keine gemischte Karte
    single = hits_of_single_source(hits)
    if single is None:
        raise HTTPException(404, f"{normalized} kommt in mehreren Wissensquellen vor")
    hits = single
    # Tabellen: Index-Snippets sind kurz, darum die ganzen Abschnitte mit dem Kennzeichen dazunehmen.
    # Ohne Gross/Klein: der Schluessel -X2:3A steht im Dokument als -X2:3a.
    table_docs = {h["document_id"]: h for h in hits if h["doc_type"] in TABLE_DOC_TYPES}
    if table_docs:
        chunks = session.execute(
            select(Chunk.document_id, Chunk.content).where(
                Chunk.document_id.in_(table_docs), Chunk.content.icontains(normalized, autoescape=True)
            )
        ).all()
        for document_id, content in chunks:
            hits.append({**table_docs[document_id], "context": content})
    # Kopfzeile der Stueckliste ("Anlage =FB1, Schaltschrank +ST1, Feld +FE1") fuer den Klartext der Orte
    legend = ""
    bom_ids = {h["document_id"] for h in hits if h["doc_type"] == "bom"}
    if bom_ids:
        legend = "\n".join(
            session.scalars(
                select(Chunk.content)
                .where(Chunk.document_id.in_(bom_ids), Chunk.content.contains("Anlage", autoescape=True))
                .limit(3)
            )
        )
    card = build_fact_card(normalized, hits, legend)
    if card is None:
        raise HTTPException(404, f"Keine Befunde zu {normalized}")
    return card
