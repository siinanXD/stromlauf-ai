"""Anmeldung per Magic-Link und Ausgabe des JWT.

POST /api/auth/magic-link {email}  -> Link per Mail (SMTP_URL) oder, mit AUTH_DEV_LINK=true, in der Antwort
POST /api/auth/exchange   {token}  -> JWT + Workspace; erste Anmeldung legt Nutzer und Workspace an
GET  /api/auth/me                  -> wer bin ich, welcher Workspace, welche Rolle
GET  /api/auth/mode                -> jwt | legacy (kein JWT_SECRET: API_KEY oder offen)
"""

import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, current_principal, issue_token
from app.config import get_settings
from app.db import get_session
from app.models import LoginToken, User, Workspace, WorkspaceMember

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

TOKEN_MINUTES = 15


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkOut(BaseModel):
    sent: bool
    dev_link: str | None = None


class ExchangeRequest(BaseModel):
    token: str


class WorkspaceOut(BaseModel):
    id: str
    name: str
    role: str


class ExchangeOut(BaseModel):
    token: str
    expires_at: datetime
    email: str
    workspace: WorkspaceOut


class MeOut(BaseModel):
    email: str | None
    user_id: str | None
    workspace: WorkspaceOut
    via: str


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _send_mail(to: str, link: str) -> None:
    settings = get_settings()
    url = urlsplit(settings.smtp_url or "")
    if not url.hostname:
        raise RuntimeError("SMTP_URL fehlt")
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = "Anmeldung bei Stromlauf AI"
    message.set_content(f"Dein Anmeldelink (15 Minuten gueltig):\n\n{link}\n")
    port = url.port or (465 if url.scheme == "smtps" else 587)
    client = smtplib.SMTP_SSL(url.hostname, port, timeout=15) if url.scheme == "smtps" else smtplib.SMTP(url.hostname, port, timeout=15)
    with client:
        if url.scheme != "smtps":
            client.starttls()
        if url.username:
            client.login(url.username, url.password or "")
        client.send_message(message)


@router.get("/mode")
def auth_mode():
    settings = get_settings()
    return {"mode": "jwt" if settings.jwt_secret else "legacy", "dev_link": settings.auth_dev_link}


@router.post("/magic-link", response_model=MagicLinkOut, status_code=202)
def request_magic_link(body: MagicLinkRequest, session: Session = Depends(get_session)):
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(409, "Anmeldung per Link ist nicht aktiv (JWT_SECRET fehlt)")
    email = body.email.lower().strip()
    raw = secrets.token_urlsafe(32)
    session.add(
        LoginToken(email=email, token_hash=_hash(raw), expires_at=datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES))
    )
    session.commit()
    link = f"{settings.frontend_url.rstrip('/')}/login/exchange?token={raw}"
    if settings.smtp_url:
        try:
            _send_mail(email, link)
        except Exception as exc:  # noqa: BLE001 - Mailversand ist ein externer Dienst
            logger.exception("Magic-Link-Mail fehlgeschlagen")
            raise HTTPException(502, f"Mail konnte nicht gesendet werden: {type(exc).__name__}") from exc
        return MagicLinkOut(sent=True, dev_link=link if settings.auth_dev_link else None)
    logger.info("Magic-Link fuer %s (kein SMTP_URL): %s", email, link)
    if not settings.auth_dev_link:
        raise HTTPException(502, "Kein Mailversand konfiguriert (SMTP_URL) und AUTH_DEV_LINK ist aus")
    return MagicLinkOut(sent=False, dev_link=link)


def _workspace_name(email: str) -> str:
    domain = email.split("@", 1)[-1]
    label = domain.split(".")[0] if domain else email
    return label.capitalize() or "Workspace"


@router.post("/exchange", response_model=ExchangeOut)
def exchange(body: ExchangeRequest, session: Session = Depends(get_session)):
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(409, "Anmeldung per Link ist nicht aktiv (JWT_SECRET fehlt)")
    login = session.scalar(select(LoginToken).where(LoginToken.token_hash == _hash(body.token)))
    now = datetime.now(timezone.utc)
    if login is None or login.used_at is not None or login.expires_at < now:
        raise HTTPException(401, "Link ungueltig oder abgelaufen; neuen Link anfordern")
    login.used_at = now
    user = session.scalar(select(User).where(User.email == login.email))
    if user is None:
        user = User(email=login.email)
        session.add(user)
        session.flush()
    membership = session.scalar(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).order_by(WorkspaceMember.created_at)
    )
    if membership is None:
        workspace = Workspace(name=_workspace_name(user.email))
        session.add(workspace)
        session.flush()
        membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin")
        session.add(membership)
        session.flush()
    workspace = session.get(Workspace, membership.workspace_id)
    session.commit()
    token, expires = issue_token(
        user_id=user.id,
        email=user.email,
        workspace_id=workspace.id,
        role=membership.role,
        secret=settings.jwt_secret,
        hours=settings.jwt_ttl_hours,
    )
    return ExchangeOut(
        token=token,
        expires_at=expires,
        email=user.email,
        workspace=WorkspaceOut(id=workspace.id, name=workspace.name, role=membership.role),
    )


@router.get("/me", response_model=MeOut)
def me(request: Request, session: Session = Depends(get_session), principal: Principal = Depends(current_principal)):
    workspace = session.get(Workspace, principal.workspace_id)
    name = workspace.name if workspace else principal.workspace_id
    return MeOut(
        email=principal.email,
        user_id=principal.user_id,
        workspace=WorkspaceOut(id=principal.workspace_id, name=name, role=principal.role),
        via=principal.via,
    )
