"""Fusion der Dokumentensuche gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1): je Modus ein Fall mit zwei
synthetischen Chunks (SIN-1232). A liegt beim Anfragevektor, B enthaelt das Suchwort."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

WS = "ws-fusion-test"


def _in_workspace(action):
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            return action(session)
    finally:
        reset_workspace(token)


def _wipe(session) -> None:
    from sqlalchemy import select

    from app.models import KnowledgeSource

    for row in session.scalars(select(KnowledgeSource)).all():
        session.delete(row)


@pytest.fixture(scope="module")
def chunks(tmp_path_factory):
    """Quelle mit Chunk A (Vektor wie die Anfrage, anderes Wort) und B (anderer Vektor, Suchwort)."""
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import session_scope
    from app.main import app
    from app.models import Chunk, Document, KnowledgeSource, Workspace

    get_settings.cache_clear()
    dim = get_settings().embedding_dim
    near, far = [1.0] + [0.0] * (dim - 1), [0.0, 1.0] + [0.0] * (dim - 2)

    def create(session):
        _wipe(session)
        source = KnowledgeSource(name="Fusion-Test")
        session.add(source)
        session.flush()
        doc = Document(source_id=source.id, filename="hb.md", storage_path="/nirgends/hb.md", doc_type="manual", status="ready")
        session.add(doc)
        session.flush()
        a = Chunk(document_id=doc.id, source_id=source.id, kind="text", content="Getriebe wird warm", embedding=near)
        b = Chunk(document_id=doc.id, source_id=source.id, kind="text", content="Motorschutz ausgelöst", embedding=far)
        session.add_all([a, b])
        session.flush()
        return {"source": source.id, "a": a.id, "b": b.id, "vector": near}

    with TestClient(app):  # lifespan legt Tabellen und die Volltextspalte an
        with session_scope() as session:
            session.merge(Workspace(id=WS, name=WS))
        yield _in_workspace(create)
        _in_workspace(_wipe)
    get_settings.cache_clear()


def _ids(chunks, limit: int, **kwargs) -> list[str]:
    from app.retrieval import hybrid_chunk_ids

    return _in_workspace(
        lambda session: hybrid_chunk_ids(session, "Motorschutz", chunks["vector"], [chunks["source"]], None, limit, **kwargs)
    )


def test_vector_findet_den_nachbarn_im_vektorraum(chunks):
    assert _ids(chunks, 1, fusion="vector") == [chunks["a"]]


def test_fulltext_findet_nur_das_suchwort(chunks):
    assert _ids(chunks, 8, fusion="fulltext") == [chunks["b"]]


def test_hybrid_liefert_beide_und_bleibt_der_standard(chunks):
    # B steht in beiden Ranglisten (Vektor Rang 2, Volltext Rang 1) und gewinnt deshalb vor A
    assert _ids(chunks, 8, fusion="vector") == [chunks["a"], chunks["b"]]
    assert _ids(chunks, 8, fusion="hybrid") == _ids(chunks, 8) == [chunks["b"], chunks["a"]]
