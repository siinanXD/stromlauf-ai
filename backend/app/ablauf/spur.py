"""Langfuse-Spur eines Ablaufs: ein Trace je Lauf, ein Kind-Span je Schritt. Ohne Tracing No-op.

Langfuse Python SDK v4 (installiert 4.15.6, Doku
https://langfuse.com/docs/observability/sdk/instrumentation): Der Wurzel-Span lebt ueber viele
Methodenaufrufe, deshalb `start_observation` mit `.end()` statt Kontextmanager; Session und Tags
setzt `propagate_attributes` (ersetzt `update_trace` aus v3). Ein Fehler im Tracing bricht den
Lauf nie ab.
"""

import logging
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

from app.tracing import langfuse_client, tracing_enabled

logger = logging.getLogger(__name__)


class _Schritt:
    def __init__(self, span=None):
        self._span = span

    def output(self, text: str) -> None:
        if self._span is None:
            return
        try:
            self._span.update(output=text)
        except Exception:  # noqa: BLE001 - Tracing darf den Schritt nie kippen
            logger.warning("Langfuse-Ausgabe nicht gesetzt", exc_info=True)


class Spur:
    def __init__(self, client=None, root=None, attrs: dict | None = None):
        self._client = client
        self._root = root
        self._attrs = attrs or {}

    @classmethod
    def fuer(cls, run_id: str, model: str) -> "Spur":
        if not tracing_enabled():
            return cls()
        try:
            from langfuse import propagate_attributes

            client = langfuse_client()
            attrs = {
                "session_id": f"run:{run_id}",
                "tags": ["stromlauf-ai", "ablauf", f"model:{model}"],
                "trace_name": "ablauf",
            }
            with propagate_attributes(**attrs):
                root = client.start_observation(
                    name="ablauf", as_type="span", input={"run_id": run_id, "model": model}
                )
            return cls(client, root, attrs)
        except Exception:  # noqa: BLE001 - ohne Trace weiterlaufen
            logger.warning("Langfuse-Spur fuer Lauf %s nicht angelegt", run_id, exc_info=True)
            return cls()

    @contextmanager
    def schritt(self, key: str, input: str) -> Iterator[_Schritt]:
        """Kind-Span des Schritts; eine Ausnahme markiert ihn als Fehler und laeuft weiter."""
        if self._root is None:
            yield _Schritt()
            return
        stack = ExitStack()
        try:
            from langfuse import propagate_attributes

            span = stack.enter_context(
                self._root.start_as_current_observation(name=key, as_type="span", input=input)
            )
            stack.enter_context(propagate_attributes(**self._attrs))
        except Exception:  # noqa: BLE001 - ohne Span weiterlaufen
            logger.warning("Langfuse-Span fuer Schritt %s nicht angelegt", key, exc_info=True)
            yield _Schritt()
            return
        try:
            yield _Schritt(span)
        except Exception as exc:
            try:
                span.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
            except Exception:  # noqa: BLE001
                logger.warning("Langfuse-Fehlerstatus nicht gesetzt", exc_info=True)
            raise
        finally:
            try:
                stack.close()
            except Exception:  # noqa: BLE001
                logger.warning("Langfuse-Span nicht beendet", exc_info=True)

    def url(self) -> str | None:
        if self._root is None:
            return None
        try:
            return self._client.get_trace_url(trace_id=self._root.trace_id)
        except Exception:  # noqa: BLE001 - Link ist Beiwerk
            logger.warning("Langfuse-Link nicht ermittelt", exc_info=True)
            return None

    def schliessen(self, status: str) -> None:
        if self._root is None:
            return
        try:
            self._root.update(output=status, level="ERROR" if status == "fehler" else None)
            self._root.end()
            self._client.flush()
        except Exception:  # noqa: BLE001
            logger.warning("Langfuse-Spur nicht abgeschlossen", exc_info=True)
