"""Lesekette ohne Datenbank (Issue #63): Upload und Ingest-Benchmark nutzen dieselben Stuecke und Kennzeichen."""

import os
from pathlib import Path

import pytest

from app.ingestion.pipeline import Piece
from app.models import TagType

FIXTURE = Path(__file__).parent / "fixtures" / "FB10_Foerderband.scl"
DB = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)
WS = "ws-pipeline-pieces-test"

PIECES = [
    Piece("-K1 zieht an, Klemme -X1:5", page=1, section="Blatt 1"),
    Piece("nochmal -K1 in anderem Wortlaut", page=1, section="Blatt 1"),
    Piece("E0.0 Start, dazu -K1", page=2, section="Blatt 2"),
]
EXPECTED_ROWS = [
    ("-K1", TagType.DEVICE, 1, "Blatt 1"),
    ("-X1", TagType.TERMINAL, 1, "Blatt 1"),
    ("-X1:5", TagType.TERMINAL, 1, "Blatt 1"),
    ("-K1", TagType.DEVICE, 2, "Blatt 2"),
    ("E0.0", TagType.PLC_ADDRESS, 2, "Blatt 2"),
]


def test_tag_rows_ein_eintrag_je_kennzeichen_typ_seite_und_abschnitt():
    from app.ingestion.pipeline import tag_rows

    rows = tag_rows(PIECES)
    assert sorted((r.tag, r.tag_type, r.page, r.section) for r in rows) == sorted(EXPECTED_ROWS)
    first = next(r for r in rows if r.tag == "-K1" and r.page == 1)
    assert "zieht an" in first.context  # der erste Fund liefert den Kontext


def test_tag_rows_beachtet_plc_loose_und_blatt_stil():
    from app.ingestion.pipeline import tag_rows

    assert [r.tag for r in tag_rows([Piece("U A 1.0", plc_loose=True)])] == ["A1.0"]
    assert tag_rows([Piece("U A 1.0")]) == []  # "A 1.0" im Fliesstext ist meist eine Stromangabe
    assert "4K1" in [r.tag for r in tag_rows([Piece("Schuetz 4K1 schaltet", folio_style=True)])]


def test_split_pieces_teilt_lange_stuecke_und_behaelt_seite_abschnitt_und_modus():
    from app.ingestion.pipeline import split_pieces

    long = Piece("-K1 " + "Text " * 2000, page=3, section="S", plc_loose=True)
    parts = split_pieces([long, Piece("kurz", page=4)])
    assert len(parts) > 2
    assert all(p.page == 3 and p.section == "S" and p.plc_loose for p in parts[:-1])
    assert parts[-1].content == "kurz" and parts[-1].page == 4


def test_document_pieces_liest_ohne_datenbank_dasselbe_wie_der_upload():
    from app.ingestion.pipeline import _build_pieces, document_pieces

    read = document_pieces(FIXTURE, "plc_program")
    pieces, page_count, note = _build_pieces("doc", FIXTURE, "plc_program", vision=False)
    assert [p.content for p in read.pieces] == [p.content for p in pieces]
    assert read.page_count is None and page_count is None and note == ""


def _wipe_sources() -> None:
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import KnowledgeSource
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            for source in session.scalars(select(KnowledgeSource)).all():
                session.delete(source)
    finally:
        reset_workspace(token)


@DB
def test_ingest_document_schreibt_je_kennzeichen_typ_seite_abschnitt_eine_zeile(monkeypatch):
    """Charakterisierung: gilt vor und nach dem Herausloesen von tag_rows unveraendert."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import session_scope
    from app.ingestion import pipeline
    from app.models import Document, KnowledgeSource, TagOccurrence, Workspace
    from app.tenancy import reset_workspace, set_workspace

    dim = get_settings().embedding_dim

    class _NullEmbeddings:
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * dim for _ in texts]

    monkeypatch.setattr(pipeline, "_build_pieces", lambda *args, **kwargs: (list(PIECES), 2, ""))
    monkeypatch.setattr(pipeline, "embeddings", _NullEmbeddings())
    with session_scope() as session:
        session.merge(Workspace(id=WS, name=WS))
    _wipe_sources()
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="Pipeline-Test")
            session.add(source)
            session.flush()
            document = Document(
                source_id=source.id,
                filename="plan.pdf",
                storage_path="/nirgends/plan.pdf",
                doc_type="schematic",
            )
            session.add(document)
            session.flush()
            document_id = document.id
    finally:
        reset_workspace(token)

    try:
        pipeline.ingest_document(document_id)
        token = set_workspace(WS)
        try:
            with session_scope() as session:
                document = session.get(Document, document_id)
                status, progress, error = document.status, document.progress, document.error
                rows = session.scalars(
                    select(TagOccurrence).where(TagOccurrence.document_id == document_id)
                ).all()
                stored = sorted((r.tag, r.tag_type, r.page, r.section) for r in rows)
        finally:
            reset_workspace(token)
    finally:
        _wipe_sources()

    assert (status, error) == ("ready", None)
    assert stored == sorted(EXPECTED_ROWS)
    assert progress == "3 Abschnitte, 5 Kennzeichen"
