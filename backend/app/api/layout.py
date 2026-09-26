"""Draufsicht einer Maschine: Grundflaeche, Skizze und Teile in mm."""

import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.plant import _get, _store_image
from app.db import get_session
from app.ingestion.cabinet_vision import load_png
from app.ingestion.layout_geometry import LAYOUT_KINDS, SHAPES, clamp_part, drop_known_tags, rebase_to_floor, to_parts
from app.ingestion.layout_vision import detect_layout
from app.ingestion.vision import render_page_png
from app.ingestion.tags import normalize_tag
from app.models import Document, LayoutPart, Machine, MachineLayout, TagOccurrence
from app.schemas import LayoutIn, LayoutOut, LayoutPartIn, LayoutPartOut, LayoutPartUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["layout"])


def layout_out(layout: MachineLayout) -> LayoutOut:
    return LayoutOut(
        id=layout.id,
        machine_id=layout.machine_id,
        width_mm=layout.width_mm,
        depth_mm=layout.depth_mm,
        has_image=bool(layout.image_path),
        document_id=layout.document_id,
        page=layout.page,
        scale_note=layout.scale_note,
        updated_at=layout.updated_at,
        parts=[LayoutPartOut.model_validate(p) for p in layout.parts],
    )


def _machine_layout(session: Session, machine_id: str) -> MachineLayout:
    machine = _get(session, Machine, machine_id, "Maschine")
    if machine.layout is None:
        raise HTTPException(404, "Keine Draufsicht angelegt")
    return machine.layout


def _check_part_fields(data: dict) -> None:
    if "kind" in data and data["kind"] not in LAYOUT_KINDS:
        raise HTTPException(400, f"kind muss eins sein von {list(LAYOUT_KINDS)}")
    if "shape" in data and data["shape"] not in SHAPES:
        raise HTTPException(400, f"shape muss eins sein von {list(SHAPES)}")
    if data.get("tag") is not None:
        data["tag"] = normalize_tag(data["tag"]) if data["tag"].strip() else ""


def _bounds(layout: MachineLayout) -> tuple[float, float]:
    """Ohne Masse wird nicht geklemmt (Grundflaeche noch unbekannt)."""
    return (layout.width_mm or float("inf"), layout.depth_mm or float("inf"))


def _apply_clamp(part: LayoutPart, layout: MachineLayout) -> None:
    width, depth = _bounds(layout)
    part.x_mm, part.y_mm, part.w_mm, part.h_mm = clamp_part(part.x_mm, part.y_mm, part.w_mm, part.h_mm, width, depth)


@router.get("/machines/{machine_id}/layout", response_model=LayoutOut)
def get_layout(machine_id: str, session: Session = Depends(get_session)):
    return layout_out(_machine_layout(session, machine_id))


@router.put("/machines/{machine_id}/layout", response_model=LayoutOut)
def put_layout(machine_id: str, body: LayoutIn, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    if body.document_id and session.get(Document, body.document_id) is None:
        raise HTTPException(400, "Dokument nicht gefunden")
    layout = machine.layout or MachineLayout(machine_id=machine.id)
    for key, value in body.model_dump().items():
        setattr(layout, key, value)
    session.add(layout)
    session.flush()
    for part in layout.parts:
        _apply_clamp(part, layout)
    session.commit()
    session.refresh(layout)
    return layout_out(layout)


@router.post("/machines/{machine_id}/layout/image", response_model=LayoutOut)
def upload_layout_image(machine_id: str, file: UploadFile = File(...), session: Session = Depends(get_session)):
    layout = _machine_layout(session, machine_id)
    target = _store_image(file)
    if layout.image_path:
        Path(layout.image_path).unlink(missing_ok=True)
    layout.image_path = str(target)
    session.commit()
    session.refresh(layout)
    return layout_out(layout)


@router.get("/machines/{machine_id}/layout/image")
def layout_image(machine_id: str, session: Session = Depends(get_session)):
    layout = _machine_layout(session, machine_id)
    if not layout.image_path or not Path(layout.image_path).exists():
        raise HTTPException(404, "Keine Skizze hinterlegt")
    return FileResponse(layout.image_path)


@router.post("/layouts/{layout_id}/parts", response_model=LayoutPartOut, status_code=201)
def create_part(layout_id: str, body: LayoutPartIn, session: Session = Depends(get_session)):
    layout = _get(session, MachineLayout, layout_id, "Draufsicht")
    data = body.model_dump()
    _check_part_fields(data)
    part = LayoutPart(layout_id=layout.id, origin="manual", **data)
    _apply_clamp(part, layout)
    session.add(part)
    session.commit()
    return LayoutPartOut.model_validate(part)


@router.patch("/layout-parts/{part_id}", response_model=LayoutPartOut)
def update_part(part_id: str, body: LayoutPartUpdate, session: Session = Depends(get_session)):
    part = _get(session, LayoutPart, part_id, "Teil")
    data = body.model_dump(exclude_unset=True)
    _check_part_fields(data)
    for key, value in data.items():
        setattr(part, key, value)
    _apply_clamp(part, part.layout)
    session.commit()
    return LayoutPartOut.model_validate(part)


@router.delete("/layout-parts/{part_id}", status_code=204)
def delete_part(part_id: str, session: Session = Depends(get_session)):
    session.delete(_get(session, LayoutPart, part_id, "Teil"))
    session.commit()


@router.get("/layouts/{layout_id}/export")
def export_layout(layout_id: str, session: Session = Depends(get_session)):
    layout = _get(session, MachineLayout, layout_id, "Draufsicht")
    body = layout_out(layout).model_dump(mode="json")
    name = "draufsicht_" + re.sub(r"[^A-Za-z0-9_-]+", "_", layout.machine.name) + ".json"
    return Response(
        json.dumps(body, ensure_ascii=False, indent=1),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/layouts/{layout_id}/detect", response_model=LayoutOut)
def detect_layout_parts(layout_id: str, session: Session = Depends(get_session)):
    """Claude Vision schlaegt Teile vor (kostet API-Tokens); Vorschlaege landen unbestaetigt."""
    layout = _get(session, MachineLayout, layout_id, "Draufsicht")
    if layout.image_path and Path(layout.image_path).exists():
        png, _, _ = load_png(Path(layout.image_path))
    elif layout.document_id and layout.page:
        document = session.get(Document, layout.document_id)
        path = Path(document.storage_path) if document else None
        if path is None or path.suffix.lower() != ".pdf":
            raise HTTPException(400, "Dokumentseite ist kein PDF")
        try:
            png = render_page_png(path, layout.page)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    else:
        raise HTTPException(400, "Keine Skizze hinterlegt")

    known: list[str] = []
    source_id = layout.machine.source_id
    if source_id:
        known = list(
            session.scalars(
                select(TagOccurrence.tag)
                .where(TagOccurrence.source_id == source_id, TagOccurrence.tag_type == "device")
                .distinct()
            )
        )
    try:
        result = detect_layout(png, known)
    except Exception as exc:
        logger.exception("Vision-Erkennung (Draufsicht) fehlgeschlagen")
        raise HTTPException(502, f"Vision-Erkennung fehlgeschlagen: {type(exc).__name__}: {exc}") from exc

    if not layout.width_mm and result["width_mm"]:
        layout.width_mm = result["width_mm"]
    if not layout.depth_mm and result["depth_mm"]:
        layout.depth_mm = result["depth_mm"]
    for old in list(layout.parts):
        if old.origin == "vision" and not old.confirmed:
            session.delete(old)
    confirmed_tags = {p.tag for p in layout.parts if p.confirmed and p.tag}
    for data in drop_known_tags(
        to_parts(rebase_to_floor(result["items"], result["floor"]), layout.width_mm, layout.depth_mm), confirmed_tags
    ):
        session.add(LayoutPart(layout_id=layout.id, origin="vision", confirmed=False, **data))
    session.commit()
    session.refresh(layout)
    return layout_out(layout)
