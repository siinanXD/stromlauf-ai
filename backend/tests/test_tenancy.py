"""Workspace-Kontext und Modell-Defaults, ohne Datenbank."""

import pytest

from app import tenancy
from app.models import KnowledgeSource


def test_kontext_setzen_und_zuruecksetzen():
    assert tenancy.current_workspace_id() is None
    token = tenancy.set_workspace("ws1")
    try:
        assert tenancy.current_workspace_id() == "ws1"
        assert tenancy.require_workspace() == "ws1"
    finally:
        tenancy.reset_workspace(token)
    assert tenancy.current_workspace_id() is None


def test_ohne_kontext_kein_default():
    with pytest.raises(RuntimeError):
        tenancy.require_workspace()


def test_same_workspace():
    class Row:
        workspace_id = "ws1"

    assert tenancy.same_workspace(Row())  # kein Kontext: keine Filterung
    token = tenancy.set_workspace("ws2")
    try:
        assert not tenancy.same_workspace(Row())
        assert tenancy.same_workspace(object())  # ohne workspace_id: unscoped Tabelle
    finally:
        tenancy.reset_workspace(token)


def test_scoped_modelle_haben_workspace_spalte():
    assert "workspace_id" in KnowledgeSource.__table__.c
    assert KnowledgeSource.__table__.c.workspace_id.server_default.arg == "default"
