"""Zugriff und Mandant je Request.

Drei Wege, der erste passende gewinnt:

1. JWT (HS256, `JWT_SECRET`): `Authorization: Bearer <jwt>`, `X-API-Key: <jwt>` oder fuer Bild-URLs
   `?token=<jwt>`. Claims: sub (user_id), email, ws (workspace_id), role, exp. Ausgestellt von
   `POST /api/auth/exchange` nach einem Magic-Link.
2. Gemeinsamer `API_KEY` (Header `X-API-Key`, `Authorization: Bearer` oder `?api_key=`): Dienst-
   zugriff fuer Skripte und den MCP-Server, arbeitet im Workspace "default" als admin.
3. Offen: nur wenn weder `JWT_SECRET` noch `API_KEY` gesetzt sind (lokale Entwicklung). Alles
   laeuft dann im Workspace "default".

`/api/health` und `/api/auth/*` sind frei. Die Middleware setzt den Workspace-Kontext
(`app.tenancy`) fuer die Dauer des Requests.
"""

import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

from app.tenancy import DEFAULT_WORKSPACE_ID, reset_workspace, set_workspace

logger = logging.getLogger(__name__)

HEADER = "x-api-key"
QUERY = "api_key"
TOKEN_QUERY = "token"
OPEN_PREFIXES = ("/api/health", "/api/auth/")
ALGORITHM = "HS256"


@dataclass(frozen=True, slots=True)
class Principal:
    workspace_id: str
    role: str = "admin"
    user_id: str | None = None
    email: str | None = None
    via: str = "open"  # jwt | api_key | open

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def issue_token(*, user_id: str, email: str, workspace_id: str, role: str, secret: str, hours: int) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    payload = {"sub": user_id, "email": email, "ws": workspace_id, "role": role, "exp": expires}
    return jwt.encode(payload, secret, algorithm=ALGORITHM), expires


def principal_from_token(token: str, secret: str) -> Principal | None:
    try:
        claims = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if not claims.get("sub") or not claims.get("ws"):
        return None
    return Principal(
        workspace_id=str(claims["ws"]),
        role=str(claims.get("role") or "member"),
        user_id=str(claims["sub"]),
        email=claims.get("email"),
        via="jwt",
    )


def _looks_like_jwt(value: str) -> bool:
    return value.count(".") == 2 and len(value) > 40


def presented_credentials(headers, query, method: str) -> list[str]:
    """Alle vorgelegten Schluessel/Token in Prioritaet: Bearer, X-API-Key, ?api_key=, ?token= (nur GET)."""
    found: list[str] = []
    authorization = headers.get("authorization") or ""
    scheme, _, bearer = authorization.partition(" ")
    if scheme.lower() == "bearer" and bearer.strip():
        found.append(bearer.strip())
    if value := headers.get(HEADER):
        found.append(value)
    if value := query.get(QUERY):
        found.append(value)
    if method == "GET" and (value := query.get(TOKEN_QUERY)):
        found.append(value)
    return found


def resolve_principal(credentials: list[str], *, api_key: str | None, jwt_secret: str | None) -> Principal | None:
    for value in credentials:
        if api_key and hmac.compare_digest(value, api_key):
            return Principal(workspace_id=DEFAULT_WORKSPACE_ID, role="admin", via="api_key")
        if jwt_secret and _looks_like_jwt(value):
            principal = principal_from_token(value, jwt_secret)
            if principal is not None:
                return principal
    if not api_key and not jwt_secret:
        return Principal(workspace_id=DEFAULT_WORKSPACE_ID, role="admin", via="open")
    return None


def is_open(path: str, method: str) -> bool:
    return not path.startswith("/api/") or method == "OPTIONS" or path.startswith(OPEN_PREFIXES)


async def auth_middleware(request: Request, call_next):
    from app.config import get_settings

    if is_open(request.url.path, request.method):
        return await call_next(request)
    settings = get_settings()
    principal = resolve_principal(
        presented_credentials(request.headers, request.query_params, request.method),
        api_key=settings.api_key,
        jwt_secret=settings.jwt_secret,
    )
    if principal is None:
        return JSONResponse(
            {"detail": "Anmeldung erforderlich (Bearer-Token, X-API-Key oder ?token=)"}, status_code=401
        )
    request.state.principal = principal
    token = set_workspace(principal.workspace_id)
    try:
        return await call_next(request)
    finally:
        reset_workspace(token)


def current_principal(request: Request) -> Principal:
    """FastAPI-Dependency fuer Handler, die Nutzer oder Rolle brauchen."""
    principal = getattr(request.state, "principal", None)
    if principal is None:
        return Principal(workspace_id=DEFAULT_WORKSPACE_ID)
    return principal
