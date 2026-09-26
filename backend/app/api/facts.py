"""Befundkarte fuer den Chat: was der Kennzeichen-Index zu einem Betriebsmittel weiss."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion.fact_card import build_fact_card
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
            "doc_type": document.doc_type,
            "filename": document.filename,
            "document_id": document.id,
            "page": occurrence.page,
            "section": occurrence.section,
            "context": occurrence.context,
        }
        for occurrence, document in session.execute(statement).all()
    ]
    # Tabellen: Index-Snippets sind kurz, darum die ganzen Abschnitte mit dem Kennzeichen dazunehmen
    table_docs = {h["document_id"]: h for h in hits if h["doc_type"] in TABLE_DOC_TYPES}
    if table_docs:
        chunks = session.execute(
            select(Chunk.document_id, Chunk.content).where(
                Chunk.document_id.in_(table_docs), Chunk.content.contains(normalized)
            )
        ).all()
        for document_id, content in chunks:
            hits.append({**table_docs[document_id], "context": content})
    card = build_fact_card(normalized, hits)
    if card is None:
        raise HTTPException(404, f"Keine Befunde zu {normalized}")
    return card
