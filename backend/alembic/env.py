"""Alembic-Umgebung: nutzt die Engine und die Modelle der App.

`alembic upgrade head` aus backend/ heraus; `init_db()` ruft dasselbe programmatisch beim Start.
Autogenerate (`alembic revision --autogenerate -m "..."`) vergleicht gegen `app.db.Base.metadata`.
"""

from sqlalchemy import engine_from_config, pool

from alembic import context
from app import models  # noqa: F401  (registriert die Tabellen an Base.metadata)
from app.config import get_settings
from app.db import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        section = dict(config.get_section(config.config_ini_section) or {})
        section["sqlalchemy.url"] = _url()
        engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(connection=connectable, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
