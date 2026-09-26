"""Gefuehrte Fehlersuche: Sitzungen je Maschine mit Pruefschritten und Instandhaltungslog."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.plant import _get
from app.api.signal import graph_for_source
from app.db import get_session
from app.ingestion.diagnosis import append_finding, build_steps
from app.ingestion.tags import TagType, extract_tags
from app.models import DiagnosisSession, FaultEntry, Machine
from app.schemas import DiagnosisFinish, DiagnosisOut, DiagnosisStart, DiagnosisUpdate

router = APIRouter(prefix="/api", tags=["diagnosis"])


def _refs(session: Session, machine: Machine) -> dict[str, str]:
    """Blatt-Verweise je Kennzeichen aus Stueckliste/Klemmenplan der verknuepften Quelle."""
    if not machine.source_id:
        return {}
    graph, _ = graph_for_source(session, machine.source_id)
    return {node.id: node.ref for node in graph.nodes.values() if node.ref.startswith("/")}


@router.get("/machines/{machine_id}/diagnoses", response_model=list[DiagnosisOut])
def list_diagnoses(machine_id: str, session: Session = Depends(get_session)):
    _get(session, Machine, machine_id, "Maschine")
    return session.scalars(
        select(DiagnosisSession)
        .where(DiagnosisSession.machine_id == machine_id)
        .order_by(DiagnosisSession.started_at.desc())
    ).all()


@router.post("/machines/{machine_id}/diagnoses", response_model=DiagnosisOut, status_code=201)
def start_diagnosis(machine_id: str, body: DiagnosisStart, session: Session = Depends(get_session)):
    machine = _get(session, Machine, machine_id, "Maschine")
    fault = session.get(FaultEntry, body.fault_id) if body.fault_id else None
    if body.fault_id and (fault is None or fault.machine_id != machine.id):
        raise HTTPException(400, "Fehlereintrag gehoert nicht zu dieser Maschine")
    title = body.title or (f"{fault.code} {fault.symptom}".strip() if fault else "Freie Fehlersuche")
    steps = build_steps(fault.fix if fault else "", list(fault.tags) if fault else [], _refs(session, machine))
    diagnosis = DiagnosisSession(machine_id=machine.id, fault_id=fault.id if fault else None, title=title[:300], steps=steps)
    session.add(diagnosis)
    session.commit()
    return diagnosis


@router.patch("/diagnoses/{diagnosis_id}", response_model=DiagnosisOut)
def update_diagnosis(diagnosis_id: str, body: DiagnosisUpdate, session: Session = Depends(get_session)):
    diagnosis = _get(session, DiagnosisSession, diagnosis_id, "Fehlersuche")
    if body.steps is not None:
        diagnosis.steps = [step.model_dump() for step in body.steps]
    if body.finding is not None:
        diagnosis.finding = body.finding
    session.commit()
    return diagnosis


@router.post("/diagnoses/{diagnosis_id}/finish", response_model=DiagnosisOut)
def finish_diagnosis(diagnosis_id: str, body: DiagnosisFinish, session: Session = Depends(get_session)):
    diagnosis = _get(session, DiagnosisSession, diagnosis_id, "Fehlersuche")
    diagnosis.outcome = body.outcome
    diagnosis.finding = body.finding.strip()
    diagnosis.finished_at = datetime.now(timezone.utc)
    if body.add_to_faults and diagnosis.finding:
        fault = session.get(FaultEntry, diagnosis.fault_id) if diagnosis.fault_id else None
        today = date.today()
        if fault is not None:
            fault.cause = append_finding(fault.cause, diagnosis.finding, today)
        else:
            tags = [t.tag for t in extract_tags(diagnosis.finding) if t.tag_type == TagType.DEVICE]
            session.add(
                FaultEntry(
                    machine_id=diagnosis.machine_id,
                    symptom=diagnosis.title,
                    cause=append_finding("", diagnosis.finding, today),
                    doc_ref="aus Fehlersuche",
                    tags=list(dict.fromkeys(tags)),
                )
            )
    session.commit()
    return diagnosis


@router.delete("/diagnoses/{diagnosis_id}", status_code=204)
def delete_diagnosis(diagnosis_id: str, session: Session = Depends(get_session)):
    session.delete(_get(session, DiagnosisSession, diagnosis_id, "Fehlersuche"))
    session.commit()
