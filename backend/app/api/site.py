"""Standortplan: Hallen mit Lage und Mini-Layout, Materialfluss zwischen Hallen, Maschinen-Kennzahlen."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.plant import _get
from app.db import get_session
from app.models import DiagnosisSession, Hall, Machine, MachineSpec, SiteFlow
from app.schemas import SiteFlowIn, SiteFlowOut, SiteHall, SiteMachine, SiteOut, SpecIn, SpecOut
from app.werk.site import check_site_flows, clean_specs, dock_count, place_halls

router = APIRouter(prefix="/api", tags=["site"])


@router.get("/site", response_model=SiteOut)
def get_site(session: Session = Depends(get_session)):
    halls = session.scalars(
        select(Hall)
        .options(
            selectinload(Hall.machines).selectinload(Machine.specs),
            selectinload(Hall.machines).selectinload(Machine.faults),
        )
        .order_by(Hall.created_at)
    ).all()
    open_by_hall = dict(
        session.execute(
            select(Machine.hall_id, func.count())
            .join(DiagnosisSession, DiagnosisSession.machine_id == Machine.id)
            .where(DiagnosisSession.outcome == "open")
            .group_by(Machine.hall_id)
        ).all()
    )
    rects = place_halls([(h.site_x, h.site_y, h.site_w, h.site_h) for h in halls])
    out = []
    for hall, (x, y, w, h) in zip(halls, rects, strict=True):
        specs = [{"label": s.label, "value": s.value} for m in hall.machines for s in m.specs]
        out.append(
            SiteHall(
                id=hall.id,
                name=hall.name,
                kind=hall.kind,
                description=hall.description,
                x=x,
                y=y,
                w=w,
                h=h,
                machine_count=len(hall.machines),
                fault_count=sum(len(m.faults) for m in hall.machines),
                open_diagnoses=open_by_hall.get(hall.id, 0),
                lines=list(dict.fromkeys(m.line for m in hall.machines if m.line)),
                docks=dock_count(specs),
                machines=[
                    SiteMachine(
                        id=m.id,
                        name=m.name,
                        machine_type=m.machine_type,
                        pos_x=m.pos_x,
                        pos_y=m.pos_y,
                        line=m.line,
                    )
                    for m in hall.machines
                ],
            )
        )
    flows = session.scalars(select(SiteFlow)).all()
    return SiteOut(halls=out, flows=[SiteFlowOut.model_validate(f) for f in flows])


@router.put("/site/flows", response_model=list[SiteFlowOut])
def replace_site_flows(body: list[SiteFlowIn], session: Session = Depends(get_session)):
    hall_ids = set(session.scalars(select(Hall.id)).all())
    try:
        check_site_flows([(f.from_hall_id, f.to_hall_id) for f in body], hall_ids)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err
    session.execute(delete(SiteFlow))
    flows = [SiteFlow(**f.model_dump()) for f in body]
    session.add_all(flows)
    session.commit()
    return [SiteFlowOut.model_validate(f) for f in flows]


@router.get("/machines/{machine_id}/specs", response_model=list[SpecOut])
def list_specs(machine_id: str, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    return [SpecOut.model_validate(s) for s in machine.specs]


@router.put("/machines/{machine_id}/specs", response_model=list[SpecOut])
def replace_specs(machine_id: str, body: list[SpecIn], session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    rows = clean_specs([s.model_dump() for s in body])
    machine.specs.clear()
    session.flush()
    machine.specs.extend(MachineSpec(machine_id=machine.id, **row) for row in rows)
    session.commit()
    session.refresh(machine)
    return [SpecOut.model_validate(s) for s in machine.specs]
