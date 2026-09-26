"""Werk: Hallen, Maschinen, Fehlerlisten, Schaltschrankbilder mit Hotspots."""

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import get_session
from app.ingestion.cabinet_vision import detect_components, image_size
from app.ingestion.tags import normalize_tag, search_prefixes
from app.models import (
    CabinetHotspot,
    CabinetImage,
    Document,
    FaultEntry,
    Hall,
    HallFlow,
    KnowledgeSource,
    Machine,
    MachineType,
    TagOccurrence,
)
from app.schemas import (
    CabinetOut,
    FaultIn,
    FaultOut,
    FlowIn,
    FlowOut,
    HallCreate,
    HallDetail,
    HallOut,
    HallUpdate,
    HotspotIn,
    HotspotOut,
    HotspotUpdate,
    MachineCreate,
    MachineDetail,
    MachineOut,
    MachineUpdate,
    TagHit,
    TagLookup,
    TagSearchHit,
    TagSearchMachine,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["plant"])

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _image_dir() -> Path:
    path = get_settings().data_dir / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_image(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(415, f"Bildformat {suffix or '(ohne)'} nicht unterstuetzt: {sorted(IMAGE_SUFFIXES)}")
    target = _image_dir() / f"{uuid.uuid4().hex}{suffix}"
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return target


def _get(session: Session, model, item_id: str, label: str):
    item = session.get(model, item_id)
    if item is None:
        raise HTTPException(404, f"{label} nicht gefunden")
    return item


def _machine_out(session: Session, machine: Machine) -> MachineOut:
    documents = 0
    if machine.source_id:
        documents = session.scalar(
            select(func.count()).select_from(Document).where(Document.source_id == machine.source_id)
        ) or 0
    return MachineOut(
        id=machine.id,
        hall_id=machine.hall_id,
        name=machine.name,
        machine_type=machine.machine_type,
        description=machine.description,
        source_id=machine.source_id,
        source_name=machine.source.name if machine.source else None,
        has_image=bool(machine.image_path),
        pos_x=machine.pos_x,
        pos_y=machine.pos_y,
        order_index=machine.order_index,
        fault_count=len(machine.faults),
        cabinet_count=len(machine.cabinets),
        document_count=documents,
    )


# --- Hallen ---------------------------------------------------------------------------------


@router.get("/halls", response_model=list[HallOut])
def list_halls(session: Session = Depends(get_session)):
    halls = session.scalars(select(Hall).options(selectinload(Hall.machines)).order_by(Hall.created_at)).all()
    return [HallOut(id=h.id, name=h.name, description=h.description, created_at=h.created_at, machine_count=len(h.machines)) for h in halls]


@router.post("/halls", response_model=HallOut, status_code=201)
def create_hall(body: HallCreate, session: Session = Depends(get_session)):
    hall = Hall(name=body.name, description=body.description)
    session.add(hall)
    session.commit()
    return HallOut(id=hall.id, name=hall.name, description=hall.description, created_at=hall.created_at)


@router.get("/halls/{hall_id}", response_model=HallDetail)
def get_hall(hall_id: str, session: Session = Depends(get_session)):
    hall = _get(session, Hall, hall_id, "Halle")
    return HallDetail(
        id=hall.id,
        name=hall.name,
        description=hall.description,
        created_at=hall.created_at,
        machine_count=len(hall.machines),
        machines=[_machine_out(session, m) for m in hall.machines],
        flows=[FlowOut.model_validate(f) for f in hall.flows],
    )


@router.patch("/halls/{hall_id}", response_model=HallOut)
def update_hall(hall_id: str, body: HallUpdate, session: Session = Depends(get_session)):
    hall = _get(session, Hall, hall_id, "Halle")
    if body.name is not None:
        hall.name = body.name
    if body.description is not None:
        hall.description = body.description
    session.commit()
    return HallOut(id=hall.id, name=hall.name, description=hall.description, created_at=hall.created_at, machine_count=len(hall.machines))


@router.delete("/halls/{hall_id}", status_code=204)
def delete_hall(hall_id: str, session: Session = Depends(get_session)):
    hall = _get(session, Hall, hall_id, "Halle")
    for machine in hall.machines:
        _remove_machine_files(machine)
    session.delete(hall)
    session.commit()


@router.put("/halls/{hall_id}/flows", response_model=list[FlowOut])
def replace_flows(hall_id: str, body: list[FlowIn], session: Session = Depends(get_session)):
    hall = _get(session, Hall, hall_id, "Halle")
    machine_ids = {m.id for m in hall.machines}
    for flow in body:
        if flow.from_machine_id not in machine_ids or flow.to_machine_id not in machine_ids:
            raise HTTPException(400, "Fluss verweist auf eine Maschine ausserhalb der Halle")
    hall.flows.clear()
    session.flush()
    for flow in body:
        session.add(HallFlow(hall_id=hall.id, **flow.model_dump()))
    session.commit()
    session.refresh(hall)
    return [FlowOut.model_validate(f) for f in hall.flows]


# --- Maschinen ------------------------------------------------------------------------------


def _remove_machine_files(machine: Machine) -> None:
    paths = [machine.image_path] + [c.image_path for c in machine.cabinets]
    if machine.layout:
        paths.append(machine.layout.image_path)
    for path in paths:
        if path:
            Path(path).unlink(missing_ok=True)


def _validate_source(session: Session, source_id: str | None) -> None:
    if source_id and session.get(KnowledgeSource, source_id) is None:
        raise HTTPException(400, "Wissensquelle nicht gefunden")


@router.post("/halls/{hall_id}/machines", response_model=MachineOut, status_code=201)
def create_machine(hall_id: str, body: MachineCreate, session: Session = Depends(get_session)):
    hall = _get(session, Hall, hall_id, "Halle")
    _validate_source(session, body.source_id)
    if body.machine_type not in set(MachineType):
        raise HTTPException(400, f"machine_type muss eins sein von {sorted(MachineType)}")
    machine = Machine(hall_id=hall.id, order_index=len(hall.machines), **body.model_dump())
    session.add(machine)
    session.commit()
    session.refresh(machine)
    return _machine_out(session, machine)


@router.get("/machines/{machine_id}", response_model=MachineDetail)
def get_machine(machine_id: str, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    base = _machine_out(session, machine)
    return MachineDetail(
        **base.model_dump(),
        faults=[FaultOut.model_validate(f) for f in machine.faults],
        cabinets=[CabinetOut.model_validate(c) for c in machine.cabinets],
    )


@router.patch("/machines/{machine_id}", response_model=MachineOut)
def update_machine(machine_id: str, body: MachineUpdate, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    data = body.model_dump(exclude_unset=True)
    if data.pop("clear_source", False):
        machine.source_id = None
    if "source_id" in data:
        _validate_source(session, data["source_id"])
    if "machine_type" in data and data["machine_type"] not in set(MachineType):
        raise HTTPException(400, f"machine_type muss eins sein von {sorted(MachineType)}")
    for key, value in data.items():
        setattr(machine, key, value)
    session.commit()
    session.refresh(machine)
    return _machine_out(session, machine)


@router.delete("/machines/{machine_id}", status_code=204)
def delete_machine(machine_id: str, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    _remove_machine_files(machine)
    session.delete(machine)
    session.commit()


@router.post("/machines/{machine_id}/image", response_model=MachineOut)
def upload_machine_image(machine_id: str, file: UploadFile = File(...), session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    target = _store_image(file)
    if machine.image_path:
        Path(machine.image_path).unlink(missing_ok=True)
    machine.image_path = str(target)
    session.commit()
    session.refresh(machine)
    return _machine_out(session, machine)


@router.get("/machines/{machine_id}/image")
def machine_image(machine_id: str, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    if not machine.image_path or not Path(machine.image_path).exists():
        raise HTTPException(404, "Kein Bild hinterlegt")
    return FileResponse(machine.image_path)


# --- Fehlerliste ----------------------------------------------------------------------------


@router.post("/machines/{machine_id}/faults", response_model=FaultOut, status_code=201)
def create_fault(machine_id: str, body: FaultIn, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    fault = FaultEntry(machine_id=machine.id, **body.model_dump())
    fault.tags = [normalize_tag(t) for t in body.tags if t.strip()]
    session.add(fault)
    session.commit()
    return FaultOut.model_validate(fault)


@router.patch("/faults/{fault_id}", response_model=FaultOut)
def update_fault(fault_id: str, body: FaultIn, session: Session = Depends(get_session)):
    fault = _get(session, FaultEntry, fault_id, "Fehlereintrag")
    for key, value in body.model_dump().items():
        setattr(fault, key, value)
    fault.tags = [normalize_tag(t) for t in body.tags if t.strip()]
    session.commit()
    return FaultOut.model_validate(fault)


@router.delete("/faults/{fault_id}", status_code=204)
def delete_fault(fault_id: str, session: Session = Depends(get_session)):
    session.delete(_get(session, FaultEntry, fault_id, "Fehlereintrag"))
    session.commit()


# --- Schaltschrank --------------------------------------------------------------------------


@router.post("/machines/{machine_id}/cabinets", response_model=CabinetOut, status_code=201)
def upload_cabinet(
    machine_id: str,
    file: UploadFile = File(...),
    title: str = Form("Schaltschrank"),
    session: Session = Depends(get_session),
):
    machine = _get(session, Machine, machine_id, "Maschine")
    target = _store_image(file)
    width, height = image_size(target)
    cabinet = CabinetImage(machine_id=machine.id, title=title.strip() or "Schaltschrank", image_path=str(target), width=width, height=height)
    session.add(cabinet)
    session.commit()
    session.refresh(cabinet)
    return CabinetOut.model_validate(cabinet)


@router.get("/cabinets/{cabinet_id}", response_model=CabinetOut)
def get_cabinet(cabinet_id: str, session: Session = Depends(get_session)):
    return CabinetOut.model_validate(_get(session, CabinetImage, cabinet_id, "Schaltschrankbild"))


@router.get("/cabinets/{cabinet_id}/image")
def cabinet_image(cabinet_id: str, session: Session = Depends(get_session)):
    cabinet = _get(session, CabinetImage, cabinet_id, "Schaltschrankbild")
    if not Path(cabinet.image_path).exists():
        raise HTTPException(404, "Bilddatei fehlt")
    return FileResponse(cabinet.image_path)


@router.delete("/cabinets/{cabinet_id}", status_code=204)
def delete_cabinet(cabinet_id: str, session: Session = Depends(get_session)):
    cabinet = _get(session, CabinetImage, cabinet_id, "Schaltschrankbild")
    Path(cabinet.image_path).unlink(missing_ok=True)
    session.delete(cabinet)
    session.commit()


@router.post("/cabinets/{cabinet_id}/hotspots", response_model=HotspotOut, status_code=201)
def create_hotspot(cabinet_id: str, body: HotspotIn, session: Session = Depends(get_session)):
    cabinet = _get(session, CabinetImage, cabinet_id, "Schaltschrankbild")
    data = body.model_dump()
    data["tag"] = normalize_tag(data["tag"]) if data["tag"].strip() else ""
    hotspot = CabinetHotspot(cabinet_id=cabinet.id, origin="manual", **data)
    session.add(hotspot)
    session.commit()
    return HotspotOut.model_validate(hotspot)


@router.patch("/hotspots/{hotspot_id}", response_model=HotspotOut)
def update_hotspot(hotspot_id: str, body: HotspotUpdate, session: Session = Depends(get_session)):
    hotspot = _get(session, CabinetHotspot, hotspot_id, "Hotspot")
    data = body.model_dump(exclude_unset=True)
    if "tag" in data:
        data["tag"] = normalize_tag(data["tag"]) if (data["tag"] or "").strip() else ""
    for key, value in data.items():
        setattr(hotspot, key, value)
    session.commit()
    return HotspotOut.model_validate(hotspot)


@router.delete("/hotspots/{hotspot_id}", status_code=204)
def delete_hotspot(hotspot_id: str, session: Session = Depends(get_session)):
    session.delete(_get(session, CabinetHotspot, hotspot_id, "Hotspot"))
    session.commit()


@router.post("/cabinets/{cabinet_id}/detect", response_model=CabinetOut)
def detect_cabinet(cabinet_id: str, session: Session = Depends(get_session)):
    """Claude Vision schlaegt Bauteile vor; Vorschlaege landen unbestaetigt in den Hotspots."""
    cabinet = _get(session, CabinetImage, cabinet_id, "Schaltschrankbild")
    machine = cabinet.machine
    known: list[str] = []
    if machine.source_id:
        known = list(
            session.scalars(
                select(TagOccurrence.tag)
                .where(TagOccurrence.source_id == machine.source_id, TagOccurrence.tag_type == "device")
                .distinct()
            )
        )
    try:
        items = detect_components(Path(cabinet.image_path), known)
    except Exception as exc:
        logger.exception("Vision-Erkennung fehlgeschlagen")
        raise HTTPException(502, f"Vision-Erkennung fehlgeschlagen: {type(exc).__name__}: {exc}") from exc

    # alte, unbestaetigte Vorschlaege ersetzen, bestaetigte behalten
    for old in list(cabinet.hotspots):
        if old.origin == "vision" and not old.confirmed:
            session.delete(old)
    for item in items:
        session.add(CabinetHotspot(cabinet_id=cabinet.id, origin="vision", confirmed=False, **item))
    session.commit()
    session.refresh(cabinet)
    return CabinetOut.model_validate(cabinet)


# --- Kennzeichen einer Maschine nachschlagen (Klick auf Hotspot) -----------------------------


@router.get("/machines/{machine_id}/tags/{tag}", response_model=TagLookup)
def lookup_tag(machine_id: str, tag: str, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    normalized = normalize_tag(tag)
    if not machine.source_id:
        return TagLookup(tag=normalized, hits=[])
    rows = session.execute(
        select(TagOccurrence, Document)
        .join(Document, TagOccurrence.document_id == Document.id)
        .where(
            TagOccurrence.source_id == machine.source_id,
            or_(
                TagOccurrence.tag == normalized,
                TagOccurrence.tag.like(f"{normalized}:%"),
                TagOccurrence.tag.like(f"%{normalized}"),
            ),
        )
        .order_by(Document.doc_type, Document.filename, TagOccurrence.page, TagOccurrence.id)
        .limit(60)
    ).all()
    hits = [
        TagHit(document_id=d.id, filename=d.filename, doc_type=d.doc_type, page=o.page, section=o.section, context=o.context)
        for o, d in rows
    ]
    bom = next((h.context for h in hits if h.doc_type == "bom"), None)
    return TagLookup(tag=normalized, hits=hits, bom_line=bom)


# --- Globale Suche nach Kennzeichen ---------------------------------------------------------


@router.get("/tags/search", response_model=list[TagSearchHit])
def search_tags(q: str = "", session: Session = Depends(get_session)):
    prefixes = search_prefixes(q)
    if not prefixes:
        return []
    escaped = [p.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%" for p in prefixes]
    rows = session.execute(
        select(TagOccurrence.tag, TagOccurrence.tag_type, func.count())
        .where(or_(*(TagOccurrence.tag.like(pattern, escape="\\") for pattern in escaped)))
        .group_by(TagOccurrence.tag, TagOccurrence.tag_type)
        .order_by(func.length(TagOccurrence.tag), TagOccurrence.tag)
        .limit(30)
    ).all()
    if not rows:
        return []
    tags = [r[0] for r in rows]
    sources: dict[str, set[str]] = {}
    for tag, source_id in session.execute(
        select(TagOccurrence.tag, TagOccurrence.source_id).where(TagOccurrence.tag.in_(tags)).distinct()
    ):
        sources.setdefault(tag, set()).add(source_id)
    machines_by_source: dict[str, list[TagSearchMachine]] = {}
    for machine in session.scalars(select(Machine).where(Machine.source_id.is_not(None)).order_by(Machine.name)):
        machines_by_source.setdefault(machine.source_id, []).append(TagSearchMachine(id=machine.id, name=machine.name))
    return [
        TagSearchHit(
            tag=tag,
            tag_type=str(tag_type),
            occurrences=count,
            machines=[m for s in sorted(sources.get(tag, ())) for m in machines_by_source.get(s, [])],
        )
        for tag, tag_type, count in rows
    ]
