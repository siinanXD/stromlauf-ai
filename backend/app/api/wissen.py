"""Gelerntes Wissen einer Maschine (app/wissen/).

GET    /api/machines/{id}/notes                  -> alle Notizen, gesperrte zuerst
POST   /api/machines/{id}/notes {text, belege}   -> von Hand ergänzen (gesperrt)
PATCH  /api/machines/{id}/notes/{note_id}        -> bearbeiten und sperren
DELETE /api/machines/{id}/notes/{note_id}        -> löschen
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Document, Machine, MachineNote
from app.schemas import NoteIn, NoteOut, NotePatch
from app.tenancy import same_workspace
from app.wissen import dienst
from app.wissen.lernen import normalisiert

router = APIRouter(prefix="/api", tags=["wissen"])


def _machine(session: Session, machine_id: str) -> Machine:
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    return machine


def _note(session: Session, machine: Machine, note_id: str) -> MachineNote:
    note = session.get(MachineNote, note_id)
    if note is None or note.machine_id != machine.id or not same_workspace(note):
        raise HTTPException(404, "Notiz nicht gefunden")
    return note


@router.get("/machines/{machine_id}/notes")
def list_notes(machine_id: str, session: Session = Depends(get_session)) -> list[NoteOut]:
    machine = _machine(session, machine_id)
    return dienst.notizen_ausgeben(session, dienst.notizen_fuer(session, machine.id, limit=None))


@router.post("/machines/{machine_id}/notes", status_code=201)
def create_note(
    machine_id: str, body: NoteIn, response: Response, session: Session = Depends(get_session)
) -> NoteOut:
    machine = _machine(session, machine_id)
    ids = {b.document_id for b in body.belege}
    gueltig = set(
        session.scalars(
            select(Document.id).where(Document.id.in_(ids), Document.source_id == machine.source_id)
        )
    )
    if gueltig != ids:
        raise HTTPException(400, "Beleg verweist auf ein Dokument, das nicht zur Maschine gehört")
    schluessel = normalisiert(body.text)
    for vorhanden in dienst.notizen_fuer(session, machine.id, limit=None):
        if normalisiert(vorhanden.text) == schluessel:
            response.status_code = 200
            return dienst.note_out(session, vorhanden)
    note = MachineNote(
        machine_id=machine.id,
        text=" ".join(body.text.split()),
        quelle="mensch",
        belege=[b.model_dump() for b in body.belege],
        gesperrt=True,
    )
    session.add(note)
    session.flush()
    session.commit()
    dienst.schreibe_obsidian(session, machine)
    return dienst.note_out(session, note)


@router.patch("/machines/{machine_id}/notes/{note_id}")
def update_note(
    machine_id: str, note_id: str, body: NotePatch, session: Session = Depends(get_session)
) -> NoteOut:
    machine = _machine(session, machine_id)
    note = _note(session, machine, note_id)
    if body.text is not None:
        note.text = " ".join(body.text.split())
    note.gesperrt = True
    note.quelle = "mensch"
    session.flush()
    session.commit()
    dienst.schreibe_obsidian(session, machine)
    return dienst.note_out(session, note)


@router.delete("/machines/{machine_id}/notes/{note_id}", status_code=204)
def delete_note(machine_id: str, note_id: str, session: Session = Depends(get_session)) -> Response:
    machine = _machine(session, machine_id)
    session.delete(_note(session, machine, note_id))
    session.flush()
    session.commit()
    dienst.schreibe_obsidian(session, machine)
    return Response(status_code=204)
