"""Auswahl und DSN-Umwandlung des Checkpointers, ohne Datenbank."""

import asyncio
from types import SimpleNamespace

import pytest

from app import checkpointer


def test_sqlalchemy_url_wird_libpq_dsn():
    assert (
        checkpointer.postgres_dsn("postgresql+psycopg://u:p@db:5432/stromlauf")
        == "postgresql://u:p@db:5432/stromlauf"
    )
    assert checkpointer.postgres_dsn("postgres://u:p@db/x") == "postgresql://u:p@db/x"


def test_nicht_postgres_wird_abgelehnt():
    with pytest.raises(ValueError):
        checkpointer.postgres_dsn("sqlite:///x.db")
    with pytest.raises(ValueError):
        checkpointer.postgres_dsn("kein-schema")


def test_unbekannter_checkpointer_bricht_ab(monkeypatch):
    monkeypatch.setattr(
        checkpointer, "get_settings", lambda: SimpleNamespace(checkpointer="redis", database_url="", checkpoint_db="x")
    )

    async def run():
        async with checkpointer.open_checkpointer():
            pass

    with pytest.raises(RuntimeError):
        asyncio.run(run())
