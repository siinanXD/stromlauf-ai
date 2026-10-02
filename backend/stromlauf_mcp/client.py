"""HTTP-Zugriff auf die laufende Stromlauf-API; Fehler als verstaendliche ToolError-Meldung."""

from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

START_HINT = "Backend starten: cd backend && .venv/Scripts/uvicorn app.main:app --port 8010"


class StromlaufClient:
    def __init__(
        self,
        api_url: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120.0,
        api_key: str | None = None,
    ):
        self.api_url = api_url.rstrip("/")
        # Verbindungsaufbau kurz (Backend aus = schnell melden), Antwort lang (erste Suche laedt das Modell)
        self._http = httpx.Client(
            base_url=self.api_url,
            timeout=httpx.Timeout(timeout, connect=3.0),
            transport=transport,
            headers={"X-API-Key": api_key} if api_key else {},
        )

    def get(self, path: str, **params: Any) -> Any:
        return self._send("GET", path, params={k: v for k, v in params.items() if v is not None})

    def _send(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout) as err:
            raise ToolError(f"Stromlauf-Backend nicht erreichbar unter {self.api_url}. {START_HINT}") from err
        except httpx.TimeoutException as err:
            raise ToolError(
                "Stromlauf-Backend antwortet nicht (Zeitüberschreitung). Bei der ersten Dokumentensuche lädt "
                "das Embedding-Modell; bitte gleich erneut versuchen."
            ) from err
        except httpx.TransportError as err:
            raise ToolError(f"Stromlauf-Backend nicht erreichbar unter {self.api_url}. {START_HINT}") from err
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            if isinstance(detail, list):  # Validierungsfehler von FastAPI
                detail = "; ".join(
                    f"{'.'.join(str(part) for part in item.get('loc', [])[1:])}: {item.get('msg', item)}"
                    for item in detail
                )
            elif isinstance(detail, dict) and "message" in detail:  # 404 mit Grund, etwa beim Signalweg
                detail = detail["message"]
            raise ToolError(f"Stromlauf meldet {response.status_code}: {detail}")
        return response.json() if response.content else None
