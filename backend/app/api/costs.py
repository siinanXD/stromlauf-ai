"""Kostenbuch nach aussen (app/ledger.py).

GET   /api/machines/estimate?pages=&photos=&vision=  -> Schaetzung vor der Ingestion
GET   /api/machines/{id}/costs                       -> je Zweck, laufender Monat, gesamt
GET   /api/workspace/budget                          -> Monatsverbrauch und Limit des Workspace
PATCH /api/workspace/budget {cap_cents}              -> Limit setzen (admin), null = kein Limit
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import ledger
from app.auth import Principal, current_principal
from app.db import get_session
from app.models import Machine, Workspace
from app.tenancy import current_workspace_id, same_workspace

router = APIRouter(prefix="/api", tags=["costs"])


class BudgetPatch(BaseModel):
    cap_cents: int | None = Field(default=None, ge=0, description="null = kein Limit")


@router.get("/machines/estimate")
def estimate(
    pages: int = Query(0, ge=0, le=100_000),
    photos: int = Query(0, ge=0, le=10_000),
    vision: bool = True,
    session: Session = Depends(get_session),
) -> dict:
    return ledger.estimate(session, pages, photos, vision)


@router.get("/machines/{machine_id}/costs")
def machine_costs(machine_id: str, session: Session = Depends(get_session)) -> dict:
    machine = session.get(Machine, machine_id)
    if machine is None or not same_workspace(machine):
        raise HTTPException(404, "Maschine nicht gefunden")
    return ledger.machine_costs(session, machine_id)


@router.get("/workspace/budget")
def workspace_budget(session: Session = Depends(get_session)) -> dict:
    return ledger.workspace_month(session)


@router.patch("/workspace/budget")
def set_workspace_budget(
    body: BudgetPatch, session: Session = Depends(get_session), principal: Principal = Depends(current_principal)
) -> dict:
    if not principal.is_admin:
        raise HTTPException(403, "Nur ein Admin darf das Limit aendern")
    workspace = session.get(Workspace, current_workspace_id() or "default")
    if workspace is None:
        raise HTTPException(404, "Workspace nicht gefunden")
    workspace.monthly_ai_cap_cents = body.cap_cents
    session.commit()
    return ledger.workspace_month(session)
