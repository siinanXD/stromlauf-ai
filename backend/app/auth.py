"""Zugriffsschutz: ein gemeinsamer API-Key fuer alle /api-Routen.

Ohne API_KEY in .env bleibt das Backend offen (lokale Entwicklung). Mit API_KEY muss jede
Anfrage an /api/* den Schluessel mitschicken; nur /api/health bleibt frei, damit das Frontend
den Verbindungsstatus zeigen kann. Bilder laedt der Browser per <img src>, ohne Header;
deshalb gilt auch der Query-Parameter api_key. Das ist ein Netzschutz fuer eine Installation,
keine Benutzerverwaltung: alle Nutzer teilen sich einen Schluessel.
"""

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

HEADER = "x-api-key"
QUERY = "api_key"
OPEN_PATHS = frozenset({"/api/health"})


def presented_key(headers, query) -> str | None:
    """Schluessel aus X-API-Key, Authorization: Bearer oder ?api_key=."""
    if value := headers.get(HEADER):
        return value
    authorization = headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return query.get(QUERY) or None


def is_allowed(path: str, method: str, expected: str | None, presented: str | None) -> bool:
    if not expected or not path.startswith("/api/") or path in OPEN_PATHS or method == "OPTIONS":
        return True
    return presented is not None and hmac.compare_digest(presented, expected)


async def api_key_middleware(request: Request, call_next):
    from app.config import get_settings

    if is_allowed(
        request.url.path,
        request.method,
        get_settings().api_key,
        presented_key(request.headers, request.query_params),
    ):
        return await call_next(request)
    return JSONResponse(
        {"detail": "API-Key fehlt oder ist falsch (Header X-API-Key oder ?api_key=)"}, status_code=401
    )
