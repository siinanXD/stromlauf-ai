"""Mandanten (Workspaces): jede fachliche Zeile gehoert zu genau einem Workspace.

Der aktuelle Workspace liegt in einer ContextVar, gesetzt von der Auth-Middleware je Request und
von der Ingestion je Dokument. Zwei Sicherungen greifen ineinander:

1. Lesen: ein `do_orm_execute`-Listener haengt an jedes ORM-SELECT ein
   `with_loader_criteria(WorkspaceScoped, workspace_id == aktueller Workspace)`. Damit sind
   Listen, Suchen, Lazy-Loads und Session.get() gefiltert, ohne jede Abfrage anzufassen.
2. Schreiben: `workspace_id` hat als Python-Default `require_workspace()`. Ohne Kontext gibt es
   keine Zeile, sondern einen Fehler.

Ohne gesetzten Kontext (Skripte, Tests ohne Auth) wird nicht gefiltert; das ist Absicht fuer
Wartungsaufgaben und wird durch die API-Middleware nie erreicht.
"""

from contextvars import ContextVar, Token

from sqlalchemy import ForeignKey, String, event
from sqlalchemy.orm import Mapped, Session, mapped_column, with_loader_criteria

DEFAULT_WORKSPACE_ID = "default"

_current: ContextVar[str | None] = ContextVar("stromlauf_workspace", default=None)


def current_workspace_id() -> str | None:
    return _current.get()


def set_workspace(workspace_id: str | None) -> Token:
    return _current.set(workspace_id)


def reset_workspace(token: Token) -> None:
    _current.reset(token)


def require_workspace() -> str:
    workspace_id = _current.get()
    if workspace_id is None:
        raise RuntimeError("Kein Workspace im Kontext: Zeile kann keinem Mandanten zugeordnet werden")
    return workspace_id


def same_workspace(obj) -> bool:
    """True, wenn obj zum aktuellen Workspace gehoert (oder kein Kontext gesetzt ist)."""
    workspace_id = _current.get()
    return workspace_id is None or getattr(obj, "workspace_id", workspace_id) == workspace_id


class WorkspaceScoped:
    """Mixin fuer alle Tabellen mit Mandantenbezug."""

    workspace_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        default=require_workspace,
        server_default=DEFAULT_WORKSPACE_ID,
    )


@event.listens_for(Session, "do_orm_execute")
def _filter_by_workspace(state) -> None:
    workspace_id = _current.get()
    if workspace_id is None or not state.is_select or state.is_column_load or state.is_relationship_load:
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            WorkspaceScoped,
            lambda cls: cls.workspace_id == workspace_id,
            include_aliases=True,
        )
    )
