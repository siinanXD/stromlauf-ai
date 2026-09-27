"""Gespraechsverlauf des LangGraph-Agenten: SQLite-Datei (lokal) oder Postgres (Railway).

`CHECKPOINTER=sqlite` (Standard): `data/checkpoints.sqlite`, wie bisher.
`CHECKPOINTER=postgres`: Tabellen `checkpoints*` in derselben Datenbank wie die App
(`DATABASE_URL`); `setup()` legt sie beim Start an. Damit ueberlebt der Verlauf ein Redeploy
ohne Volume und mehrere Instanzen teilen ihn sich.
"""

from contextlib import asynccontextmanager

from app.config import get_settings


def postgres_dsn(database_url: str) -> str:
    """SQLAlchemy-URL (`postgresql+psycopg://`) -> libpq-DSN fuer den Postgres-Saver."""
    scheme, sep, rest = database_url.partition("://")
    if not sep:
        raise ValueError(f"keine Datenbank-URL: {database_url!r}")
    if scheme.split("+", 1)[0] not in ("postgresql", "postgres"):
        raise ValueError(f"CHECKPOINTER=postgres braucht eine Postgres-URL, nicht {scheme!r}")
    return "postgresql://" + rest


@asynccontextmanager
async def open_checkpointer():
    settings = get_settings()
    kind = settings.checkpointer.lower()
    if kind == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_db)) as saver:
            yield saver
    elif kind == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(postgres_dsn(settings.database_url)) as saver:
            await saver.setup()
            yield saver
    else:
        raise RuntimeError(f"CHECKPOINTER={kind!r}: erlaubt sind sqlite oder postgres")
