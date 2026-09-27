"""GET /api/machines/{id}/map: das Schema-Modell einer Maschine aus Stueckliste, Index und Draufsicht."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion.machine_map import build_map
from app.models import Chunk, Document, Machine, TagOccurrence, TagType
from app.tenancy import same_workspace

router = APIRouter(prefix="/api", tags=["machine-map"])


@router.get("/machines/{machine_id}/map")
def machine_map(machine_id: str, session: Session = Depends(get_session)) -> dict:
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    layout_tags = [(p.tag, p.label) for p in (machine.layout.parts if machine.layout else []) if p.tag]
    if not machine.source_id:
        return {"machine_id": machine_id, **build_map([], layout_tags).as_dict(), "source_id": None}

    rows = session.execute(
        select(TagOccurrence.tag, TagOccurrence.context, Document.doc_type)
        .join(Document, TagOccurrence.document_id == Document.id)
        .where(TagOccurrence.source_id == machine.source_id, TagOccurrence.tag_type == TagType.DEVICE)
        .order_by(Document.doc_type, TagOccurrence.page, TagOccurrence.id)
    ).all()
    bom_rows = [(tag, context) for tag, context, doc_type in rows if doc_type == "bom"]
    known = {tag for tag, _context, _doc_type in rows}
    bom_ids = list(
        session.scalars(select(Document.id).where(Document.source_id == machine.source_id, Document.doc_type == "bom"))
    )
    legend = ""
    if bom_ids:
        legend = "\n".join(
            session.scalars(
                select(Chunk.content).where(Chunk.document_id.in_(bom_ids), Chunk.content.contains("Anlage", autoescape=True)).limit(3)
            )
        )
    return {"machine_id": machine_id, "source_id": machine.source_id, **build_map(bom_rows, layout_tags, known, legend).as_dict()}
