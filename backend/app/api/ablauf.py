"""Ablauf: Dateien hochladen, Lauf anlegen, Zustand abfragen (Orchestrierung in app/ablauf/lauf.py)."""

import shutil
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger
from app.ablauf.gruppieren import gruppiere
from app.ablauf.lauf import halle_sichern, starte_lauf
from app.ablauf.schritte import beende, neue_schritte, starte
from app.ablauf.zeiten import kennzahlen
from app.api.sources import ALLOWED_SUFFIXES
from app.config import get_settings
from app.db import get_session
from app.ingestion.pipeline import detect_doc_type
from app.models import DocType, Document, KnowledgeSource, Run
from app.schemas import (
    GruppenAnfrage,
    GruppenVorschlag,
    RunAnswer,
    RunListItem,
    RunOut,
    RunResult,
    RunStep,
    ZeitenKennzahl,
    ZeitenOut,
)
from app.tenancy import same_workspace

router = APIRouter(prefix="/api", tags=["ablauf"])

MAX_DATEIEN = 100

DOC_TYPE_LABELS = {
    DocType.SCHEMATIC: "Stromlaufplan",
    DocType.BOM: "Stückliste",
    DocType.TERMINAL_PLAN: "Klemmenplan",
    DocType.PLC_PROGRAM: "AWL",
    DocType.PLC_SYMBOLS: "Symboltabelle",
    DocType.MANUAL: "Handbuch",
    DocType.OTHER: "Sonstiges",
}


def run_out(run: Run) -> RunOut:
    """Lauf samt Ergebnis aus `steps[*]["result"]`; Schritte ohne eigenen Trace-Link erben den des Laufs."""
    result_of = {s["key"]: s.get("result") for s in run.steps}
    steps = [
        RunStep(
            **{
                **{k: v for k, v in s.items() if k != "result"},
                "trace_url": s.get("trace_url") or run.trace_url,
            }
        )
        for s in run.steps
    ]
    modell = result_of.get("modell") or {}
    result = RunResult(
        profile=result_of.get("steckbrief"),
        map_counts=(
            {"zones": modell.get("zones", 0), "parts": modell.get("parts", 0)} if modell else None
        ),
        answers=[RunAnswer(**a) for a in result_of.get("zusammenfassung") or []] or None,
        machine_id=run.machine_id,
    )
    return RunOut(
        id=run.id,
        name=run.name,
        status=run.status,
        model=run.model,
        steps=steps,
        trace_url=run.trace_url,
        error=run.error,
        created_at=run.created_at,
        finished_at=run.finished_at,
        result=result,
    )


@router.post("/runs", response_model=RunOut, status_code=201)
def create_run(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    if not files:
        raise HTTPException(400, "Mindestens eine Datei hochladen")
    if len(files) > MAX_DATEIEN:
        raise HTTPException(400, f"Höchstens {MAX_DATEIEN} Dateien je Lauf")
    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(
                415,
                f"Dateityp {suffix or '(ohne)'} nicht unterstuetzt. Erlaubt: {sorted(ALLOWED_SUFFIXES)}",
            )
    ledger.check_budget(session)

    now = datetime.now(UTC)
    source = KnowledgeSource(name=(name.strip() or f"Lauf {now:%d.%m.%Y %H:%M}")[:200])
    session.add(source)
    session.flush()
    upload_dir = get_settings().upload_dir
    types: list[str] = []
    for file in files:
        filename = Path(file.filename or "upload").name
        suffix = Path(filename).suffix.lower()
        document_id = uuid.uuid4().hex
        path = upload_dir / f"{document_id}{suffix}"
        with path.open("wb") as target:
            shutil.copyfileobj(file.file, target)
        doc_type = detect_doc_type(filename, DocType.AUTO, path)
        session.add(
            Document(
                id=document_id,
                source_id=source.id,
                filename=filename,
                storage_path=str(path),
                doc_type=doc_type,
            )
        )
        types.append(DOC_TYPE_LABELS.get(doc_type, str(doc_type)))

    anzahl = f"{len(files)} Datei" if len(files) == 1 else f"{len(files)} Dateien"
    steps = starte(neue_schritte(), "hochladen", now.isoformat(), "")
    steps = beende(
        steps, "hochladen", datetime.now(UTC).isoformat(), f"{anzahl}: {', '.join(types)}"
    )
    run = Run(name=source.name, source_id=source.id, steps=steps, model=get_settings().ablauf_model)
    session.add(run)
    hall_id = halle_sichern(session).id
    session.commit()

    threading.Thread(
        target=starte_lauf,
        args=(run.id, request.app.state.graph, request.app.state.loop, hall_id),
        daemon=True,
    ).start()
    return run_out(run)


@router.post("/runs/gruppen", response_model=GruppenVorschlag)
def gruppen_vorschlag(body: GruppenAnfrage):
    """Ordnet abgelegte Dateien Anlagen zu (reine Abbildung, keine Dateien, keine Datenbank)."""
    return gruppiere([d.model_dump() for d in body.dateien])


def _get_run(session: Session, run_id: str) -> Run:
    run = session.get(Run, run_id)
    if run is None or not same_workspace(run):
        raise HTTPException(404, "Lauf nicht gefunden")
    return run


@router.get("/runs/zeiten", response_model=ZeitenOut)
def get_zeiten(session: Session = Depends(get_session)):
    """Kennzahlen aus den letzten 50 Läufen des Workspaces (vor `/runs/{run_id}` registriert)."""
    rows = session.scalars(select(Run).order_by(Run.created_at.desc()).limit(50)).all()
    daten = kennzahlen(
        [
            {"id": r.id, "steps": r.steps, "trace_url": r.trace_url, "created_at": r.created_at}
            for r in rows
        ]
    )
    trace_url = {r.id: r.trace_url for r in rows}

    def kennzahl(werte: dict) -> ZeitenKennzahl:
        return ZeitenKennzahl(
            **werte, langsamster_trace_url=trace_url.get(werte["langsamster_run_id"])
        )

    return ZeitenOut(
        laeufe=daten["laeufe"],
        schritte={key: kennzahl(w) for key, w in daten["schritte"].items()},
        gesamt=kennzahl(daten["gesamt"]),
        fragen=kennzahl(daten["fragen"]),
    )


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, session: Session = Depends(get_session)):
    return run_out(_get_run(session, run_id))


@router.get("/runs", response_model=list[RunListItem])
def list_runs(session: Session = Depends(get_session)):
    rows = session.scalars(select(Run).order_by(Run.created_at.desc()).limit(20)).all()
    return [RunListItem.model_validate(r, from_attributes=True) for r in rows]
