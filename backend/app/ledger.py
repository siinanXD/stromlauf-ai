"""Kostenbuch: jeder KI-Aufruf wird einem Workspace, einer Maschine und einem Zweck zugebucht.

Tabelle `ai_call_ledger` (app/models.py: AiCall). Bausteine:

- `collect(config)`: haengt einen LangChain-Callback an eine `invoke`/`astream`-Konfiguration und
  sammelt Modell und Tokens je Aufruf, ohne dass die Vision-Module ihre Signatur aendern.
- `record(session, ...)`: eine Zeile je Aufruf, Kosten aus app/flow/pricing.py in Mikro-Cent
  (1 Cent = 1_000_000 Mikro-Cent), in derselben Transaktion wie das Ergebnis.
- `check_budget(session)`: wirft BudgetExceeded, sobald der Workspace sein Monatslimit erreicht hat
  (Workspace.monthly_ai_cap_cents, None = kein Limit). Wird VOR dem Provider-Aufruf geprueft.
- `machine_costs`, `workspace_month`, `estimate`: Zahlen fuer /api/machines/{id}/costs und
  /api/machines/estimate.
"""

from __future__ import annotations

import statistics
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.flow.pricing import cost_usd
from app.models import AiCall, Machine, Workspace
from app.tenancy import current_workspace_id

MICROCENTS_PER_CENT = 1_000_000
PURPOSES = ("chat", "vision.page", "vision.cabinet", "vision.layout", "flow")

# Listenannahmen aus docs/product/cost-model.md, wenn das Kostenbuch noch keine Messwerte hat
LIST_TOKENS = {
    "vision.page": (1_500, 600),  # Seitenanalyse je Schaltplanseite
    "vision.cabinet": (1_600, 400),  # Bauteile auf einem Foto
    "flow.page": (700, 250),  # Ablauf-Extraktion, Anteil je Seite (210k in + 75k out fuer 300 Seiten)
    "chat": (8_000, 600),  # eine Antwort mit Werkzeugaufrufen
}


class BudgetExceeded(Exception):
    """Monatslimit des Workspace erreicht; der Aufrufer meldet 402."""

    def __init__(self, used_cents: float, cap_cents: int):
        self.used_cents, self.cap_cents = used_cents, cap_cents
        super().__init__(
            f"KI-Monatslimit erreicht: {used_cents / 100:.2f} von {cap_cents / 100:.2f} EUR verbraucht. "
            "Ein Admin kann das Limit unter Einstellungen erhoehen."
        )


def microcents(model: str, input_tokens: int, output_tokens: int) -> int:
    return round(cost_usd(model, input_tokens, output_tokens) * 100 * MICROCENTS_PER_CENT)


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(self.model or other.model, self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens)


def usage_of(message: Any, fallback_model: str) -> Usage | None:
    """Tokens aus einer LangChain-AIMessage (usage_metadata); None ohne Angaben (z. B. Fake-LLM in Tests)."""
    usage = getattr(message, "usage_metadata", None) or {}
    if not usage:
        return None
    metadata = getattr(message, "response_metadata", None) or {}
    model = metadata.get("model_name") or metadata.get("model") or fallback_model
    return Usage(model, int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0))


class UsageCollector(BaseCallbackHandler):
    """Sammelt Tokens aller LLM-Aufrufe, die mit dieser Konfiguration laufen (threadsicher)."""

    def __init__(self, fallback_model: str):
        self.fallback_model = fallback_model
        self.calls: list[Usage] = []
        self._lock = threading.Lock()

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        for generations in getattr(response, "generations", []) or []:
            for generation in generations:
                usage = usage_of(getattr(generation, "message", None), self.fallback_model)
                if usage is not None:
                    with self._lock:
                        self.calls.append(usage)

    def total(self) -> Usage | None:
        with self._lock:
            if not self.calls:
                return None
            total = self.calls[0]
            for usage in self.calls[1:]:
                total = total + usage
            return total


def collect(config: dict | None, model: str | None = None) -> tuple[dict, UsageCollector]:
    """Konfiguration (z. B. aus vision_trace) um den Sammler ergaenzen; Original bleibt unveraendert."""
    collector = UsageCollector(model or get_settings().vision_model)
    merged = dict(config or {})
    merged["callbacks"] = [*merged.get("callbacks", []), collector]
    return merged, collector


def record(
    session: Session,
    *,
    purpose: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    machine_id: str | None = None,
    images: int = 0,
    trace_id: str | None = None,
    provider: str = "anthropic",
) -> AiCall:
    """Eine Ledger-Zeile im aktuellen Workspace; commit macht der Aufrufer zusammen mit dem Ergebnis."""
    if purpose not in PURPOSES:
        raise ValueError(f"unbekannter Zweck {purpose!r}")
    call = AiCall(
        machine_id=machine_id,
        purpose=purpose,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        images=images,
        cost_microcents=microcents(model, input_tokens, output_tokens),
        trace_id=trace_id,
    )
    session.add(call)
    session.flush()
    return call


def record_usage(session: Session, usage: Usage | None, *, purpose: str, machine_id: str | None, images: int = 0, trace_id: str | None = None) -> AiCall | None:
    if usage is None:
        return None
    return record(
        session, purpose=purpose, model=usage.model, input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens, machine_id=machine_id, images=images, trace_id=trace_id,
    )


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _sum(session: Session, *where) -> tuple[float, int]:
    row = session.execute(
        select(func.coalesce(func.sum(AiCall.cost_microcents), 0), func.count(AiCall.id)).where(*where)
    ).one()
    return float(row[0]) / MICROCENTS_PER_CENT, int(row[1])  # sum(BigInteger) kommt als Decimal


def _by_purpose(session: Session, *where) -> dict[str, dict]:
    rows = session.execute(
        select(AiCall.purpose, func.sum(AiCall.cost_microcents), func.count(AiCall.id))
        .where(*where)
        .group_by(AiCall.purpose)
    ).all()
    return {purpose: {"cents": float(total) / MICROCENTS_PER_CENT, "calls": int(calls)} for purpose, total, calls in rows}


def workspace_month(session: Session) -> dict:
    """Verbrauch des aktuellen Workspace im laufenden Monat plus Limit (fuer Guard und UI)."""
    workspace = session.get(Workspace, current_workspace_id() or "default")
    cap = workspace.monthly_ai_cap_cents if workspace else None
    cents, calls = _sum(session, AiCall.created_at >= month_start())
    return {"month_cents": cents, "month_calls": calls, "cap_cents": cap, "exceeded": cap is not None and cents >= cap}


def check_budget(session: Session) -> None:
    """Vor jedem Provider-Aufruf: Limit = Verbrauch heisst, der naechste Aufruf wird abgelehnt."""
    state = workspace_month(session)
    if state["exceeded"]:
        raise BudgetExceeded(state["month_cents"], state["cap_cents"])


def machine_costs(session: Session, machine_id: str) -> dict:
    month = AiCall.created_at >= month_start()
    is_machine = AiCall.machine_id == machine_id
    month_cents, month_calls = _sum(session, is_machine, month)
    total_cents, total_calls = _sum(session, is_machine)
    return {
        "machine_id": machine_id,
        "month": {"cents": month_cents, "calls": month_calls, "by_purpose": _by_purpose(session, is_machine, month)},
        "total": {"cents": total_cents, "calls": total_calls, "by_purpose": _by_purpose(session, is_machine)},
        "workspace": workspace_month(session),
    }


def machine_for_source(session: Session, source_id: str | None) -> str | None:
    """Maschine zu einer Wissensquelle (Dokumente haengen nur ueber die Quelle an einer Maschine)."""
    if not source_id:
        return None
    return session.scalars(select(Machine.id).where(Machine.source_id == source_id).order_by(Machine.created_at).limit(1)).first()


def _median_cents(session: Session, purpose: str) -> float | None:
    values = list(session.scalars(select(AiCall.cost_microcents).where(AiCall.purpose == purpose).order_by(AiCall.created_at.desc()).limit(200)))
    if len(values) < 5:
        return None
    return float(statistics.median(values)) / MICROCENTS_PER_CENT


def _list_cents(purpose: str, model: str) -> float:
    input_tokens, output_tokens = LIST_TOKENS[purpose]
    return microcents(model, input_tokens, output_tokens) / MICROCENTS_PER_CENT


def estimate(session: Session, pages: int, photos: int, vision: bool = True) -> dict:
    """Schaetzung vor der Ingestion: gemessene Mediane je Aufruf, sonst Listenannahmen aus cost-model.md."""
    settings = get_settings()
    page_vision = _median_cents(session, "vision.page")
    photo = _median_cents(session, "vision.cabinet")
    basis = {"vision.page": "measured" if page_vision is not None else "list", "vision.cabinet": "measured" if photo is not None else "list"}
    page_vision = page_vision if page_vision is not None else _list_cents("vision.page", settings.vision_model)
    photo = photo if photo is not None else _list_cents("vision.cabinet", settings.vision_model)
    extraction_page = _list_cents("flow.page", settings.flow_model_strong)
    chat_answer = _list_cents("chat", settings.chat_model)
    vision_total = page_vision * pages if vision else 0.0
    total = vision_total + extraction_page * pages + photo * photos
    return {
        "pages": pages,
        "photos": photos,
        "vision": vision,
        "per_page_vision_cents": round(page_vision, 3),
        "per_page_extraction_cents": round(extraction_page, 3),
        "per_photo_cents": round(photo, 3),
        "chat_per_answer_cents": round(chat_answer, 3),
        "total_cents": round(total, 2),
        "basis": basis,
        "models": {"vision": settings.vision_model, "extraction": settings.flow_model_strong, "chat": settings.chat_model},
    }


__all__ = [
    "BudgetExceeded", "Usage", "UsageCollector", "check_budget", "collect", "estimate", "machine_costs",
    "machine_for_source", "microcents", "record", "record_usage", "usage_of", "workspace_month",
]
