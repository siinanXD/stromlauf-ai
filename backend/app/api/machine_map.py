"""GET /api/machines/{id}/map: das Schema-Modell einer Maschine aus Stueckliste und Index.

Ohne Stuecklisten-Datei (reale Exporte buendeln alles in einer PDF) kommen die Teile aus dem Kennzeichen-Index
der Planseiten und die Zonen aus deren Blatttiteln; Stuecklistenseiten in der PDF liefern Bezeichnungen (Issue #39).
Die Blattnummer einer Zone liest die Blatt-Map aus dem Schriftfeld, nicht aus der Seitenzahl (Issue #67).
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion.machine_map import Correction, build_map
from app.ingestion.page_titles import is_parts_list
from app.ingestion.pdf_layout import sheet_map
from app.ingestion.tags import normalize_tag
from app.models import Chunk, Document, Machine, MapOverride, TagOccurrence, TagType
from app.schemas import MapPartOut, MapPartPatch
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
    return machine_map_data(session, _machine(session, machine_id))


def _machine(session: Session, machine_id: str) -> Machine:
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    return machine


def _out(machine_id: str, tag: str, row: MapOverride | None) -> MapPartOut:
    return MapPartOut(
        machine_id=machine_id,
        tag=tag,
        zone_code=row.zone_code if row else None,
        label=row.label if row else None,
        hidden=row.hidden if row else False,
    )


def _override(session: Session, machine: Machine, tag: str) -> MapOverride | None:
    return session.scalar(select(MapOverride).where(MapOverride.machine_id == machine.id, MapOverride.tag == tag))


@router.patch("/machines/{machine_id}/map/parts/{tag:path}")
def correct_part(
    machine_id: str, tag: str, body: MapPartPatch, session: Session = Depends(get_session)
) -> MapPartOut:
    """Zone, Bezeichnung oder Sichtbarkeit eines Teils korrigieren. Nur genannte Felder ändern sich, null nimmt
    die Korrektur dieses Felds zurück; ist nichts mehr korrigiert, verschwindet die Zeile."""
    machine = _machine(session, machine_id)
    key = normalize_tag(tag)
    known = session.scalar(
        select(TagOccurrence.id)
        .where(
            TagOccurrence.source_id == machine.source_id,
            TagOccurrence.tag == key,
            TagOccurrence.tag_type == TagType.DEVICE,
        )
        .limit(1)
    )
    if known is None:
        raise HTTPException(404, "Teil nicht gefunden")
    row = _override(session, machine, key)
    created = row is None
    if row is None:
        row = MapOverride(machine_id=machine.id, tag=key)
    for field in body.model_fields_set:
        setattr(row, field, getattr(body, field))
    if row.zone_code is None and row.label is None and not row.hidden:
        if not created:
            session.delete(row)
        session.commit()
        return _out(machine.id, key, None)
    if created:
        session.add(row)
    session.commit()
    return _out(machine.id, key, row)


@router.delete("/machines/{machine_id}/map/parts/{tag:path}", status_code=204)
def reset_part(machine_id: str, tag: str, session: Session = Depends(get_session)) -> Response:
    """Nimmt alle Korrekturen an einem Teil zurück; ohne Korrektur passiert nichts."""
    machine = _machine(session, machine_id)
    row = _override(session, machine, normalize_tag(tag))
    if row is not None:
        session.delete(row)
        session.commit()
    return Response(status_code=204)


def machine_map_data(session: Session, machine: Machine) -> dict:
    """Modell einer Maschine; auch fuer den Ablauf (app/ablauf/lauf.py)."""
    machine_id = machine.id
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
    corrections = {
        row.tag: Correction(row.zone_code, row.label, row.hidden)
        for row in session.scalars(select(MapOverride).where(MapOverride.machine_id == machine_id))
    }
    return {
        "machine_id": machine_id,
        "source_id": machine.source_id,
        **build_map(bom_rows, known, legend, index_hits, corrections).as_dict(),
    }
