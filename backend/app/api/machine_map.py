"""GET /api/machines/{id}/map: das Schema-Modell einer Maschine aus Stueckliste und Index.

Ohne Stuecklisten-Datei (reale Exporte buendeln alles in einer PDF) kommen die Teile aus dem Kennzeichen-Index
der Planseiten und die Zonen aus deren Blatttiteln; Stuecklistenseiten in der PDF liefern Bezeichnungen (Issue #39).
Die Blattnummer einer Zone liest die Blatt-Map aus dem Schriftfeld, nicht aus der Seitenzahl (Issue #67).
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion.machine_map import build_map
from app.ingestion.page_titles import is_parts_list
from app.ingestion.pdf_layout import sheet_map
from app.models import Chunk, Document, Machine, TagOccurrence, TagType
from app.tenancy import same_workspace

router = APIRouter(prefix="/api", tags=["machine-map"])

Row = tuple[str, str, str, int | None, str | None, str | None]  # tag, context, doc_type, page, section, storage_path
Hit = tuple[str, int | None, str, int | None]  # tag, page, section, sheet
SheetOf = Callable[[str | None, int | None], int | None]


def pdf_sheets() -> SheetOf:
    """Blatt einer PDF-Seite aus dem Schriftfeld, je Datei einmal gelesen. None, wo keine Nummer gelesen wurde, auch
    wenn die Blatt-Map dort Seite = Blatt nur annimmt."""
    read: dict[str, dict[int, int]] = {}

    def sheet_of(storage_path: str | None, page: int | None) -> int | None:
        if not storage_path or page is None:
            return None
        if storage_path not in read:
            path = Path(storage_path)
            try:
                read[storage_path] = sheet_map(path).read if path.suffix.lower() == ".pdf" else {}
            except (OSError, RuntimeError):  # Datei fehlt oder ist unlesbar (PdfiumError): Zone heisst nach der Seite
                read[storage_path] = {}
        return read[storage_path].get(page)

    return sheet_of


def split_rows(rows: list[Row], sheet_of: SheetOf) -> tuple[list[tuple[str, str]], list[Hit], set[str]]:
    """(Stuecklistenzeilen, Fundstellen im Plan je Kennzeichen mit Seite, Blatttitel und Blatt, alle Kennzeichen).

    Stuecklistenzeilen sind Zeilen aus BOM-Dokumenten und von Stuecklistenseiten anderer Dokumente.
    Fundstellen sind nach Seite sortiert, damit build_map die erste Planseite eines Teils als Zone nimmt.
    """
    bom_rows: list[tuple[str, str]] = []
    index_hits: list[Hit] = []
    known: set[str] = set()
    for tag, context, doc_type, page, section, storage_path in rows:
        known.add(tag)
        if doc_type == "bom" or is_parts_list(section):
            bom_rows.append((tag, context))
        else:
            index_hits.append((tag, page, section or "", sheet_of(storage_path, page)))
    index_hits.sort(key=lambda hit: (hit[1] is None, hit[1] or 0))
    return bom_rows, index_hits, known


@router.get("/machines/{machine_id}/map")
def machine_map(machine_id: str, session: Session = Depends(get_session)) -> dict:
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    if not machine.source_id:
        return {"machine_id": machine_id, **build_map([]).as_dict(), "source_id": None}

    rows = session.execute(
        select(
            TagOccurrence.tag,
            TagOccurrence.context,
            Document.doc_type,
            TagOccurrence.page,
            TagOccurrence.section,
            Document.storage_path,
        )
        .join(Document, TagOccurrence.document_id == Document.id)
        .where(TagOccurrence.source_id == machine.source_id, TagOccurrence.tag_type == TagType.DEVICE)
        .order_by(Document.doc_type, TagOccurrence.page, TagOccurrence.id)
    ).all()
    bom_rows, index_hits, known = split_rows([tuple(row) for row in rows], pdf_sheets())
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
        **build_map(bom_rows, known, legend, index_hits).as_dict(),
    }
