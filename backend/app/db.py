from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import BACKEND_DIR, get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Schema per Alembic auf den neuesten Stand bringen (`alembic upgrade head`).

    Ersetzt `create_all` + `app.migrations`: die Baseline 0001 legt auf einer leeren Datenbank alle
    Tabellen an und bringt eine Datenbank aus der create_all-Zeit ueber dieselben additiven
    Statements auf den gleichen Stand. Neue Schemaaenderungen sind neue Revisionen unter
    backend/alembic/versions/ (`alembic revision --autogenerate -m "..."`).
    """
    from alembic.config import Config

    from alembic import command
    from app import models  # noqa: F401  (registriert die Tabellen)

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")


def get_session() -> Iterator[Session]:
    """FastAPI-Dependency."""
    with SessionLocal() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Fuer Hintergrundjobs und Agent-Tools ausserhalb eines Requests."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
