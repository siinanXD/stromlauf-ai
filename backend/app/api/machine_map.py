"""GET /api/machines/{id}/map: das Schema-Modell einer Maschine aus Stueckliste, Index und Draufsicht.

Ohne Stuecklisten-Datei (reale Exporte buendeln alles in einer PDF) kommen die Teile aus dem Kennzeichen-Index
der Planseiten und die Zonen aus deren Blatttiteln; Stuecklistenseiten in der PDF liefern Bezeichnungen (Issue #39).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion.machine_map import build_map
from app.ingestion.page_titles import is_parts_list
from app.models import Chunk, Document, Machine, TagOccurrence, TagType
from app.tenancy import same_workspace

router = APIRouter(prefix="/api", tags=["machine-map"])

Row = tuple[str, str, str, int | None, str | None]  # tag, context, doc_type, page, section


def split_rows(rows: list[Row]) -> tuple[list[tuple[str, str]], list[tuple[str, int | None, str]], set[str]]:
    """(Stuecklistenzeilen, Fundstellen im Plan je Kennzeichen mit Seite und Blatttitel, alle Kennzeichen).

    Stuecklistenzeilen sind Zeilen aus BOM-Dokumenten und von Stuecklistenseiten anderer Dokumente.
    Fundstellen sind nach Seite sortiert, damit build_map die erste Planseite eines Teils als Zone nimmt.
    """
    bom_rows: list[tuple[str, str]] = []
    index_hits: list[tuple[str, int | None, str]] = []
    known: set[str] = set()
    for tag, context, doc_type, page, section in rows:
        known.add(tag)
        if doc_type == "bom" or is_parts_list(section):
            bom_rows.append((tag, context))
        else:
            index_hits.append((tag, page, section or ""))
    index_hits.sort(key=lambda hit: (hit[1] is None, hit[1] or 0))
    return bom_rows, index_hits, known


@router.get("/machines/{machine_id}/map")
def machine_map(machine_id: str, session: Session = Depends(get_session)) -> dict:
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    layout_tags = [(p.tag, p.label) for p in (machine.layout.parts if machine.layout else []) if p.tag]
    if not machine.source_id:
        return {"machine_id": machine_id, **build_map([], layout_tags).as_dict(), "source_id": None}

    rows = session.execute(
        select(TagOccurrence.tag, TagOccurrence.context, Document.doc_type, TagOccurrence.page, TagOccurrence.section)
        .join(Document, TagOccurrence.document_id == Document.id)
        .where(TagOccurrence.source_id == machine.source_id, TagOccurrence.tag_type == TagType.DEVICE)
        .order_by(Document.doc_type, TagOccurrence.page, TagOccurrence.id)
    ).all()
    bom_rows, index_hits, known = split_rows([tuple(row) for row in rows])
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
    return {
        "machine_id": machine_id,
        "source_id": machine.source_id,
        **build_map(bom_rows, layout_tags, known, legend, index_hits).as_dict(),
    }
