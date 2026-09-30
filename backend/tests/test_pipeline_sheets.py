"""Blatt-Map in der Pipeline (Issue #67): Hinweis am Dokument, wenn sie raet; Blatttitel ueber die Blattnummer statt
ueber die Seite; locate und Zitatpruefung hinter Deckblatt und Inhaltsverzeichnis.

Docling laeuft hier nicht (wie in test_pipeline_scan.py): Die Schriftfeld-Fixtures sind Text-PDFs, ihr PDF-Rohtext
ersetzt die Docling-Seiten.
"""

import os
import shutil
from pathlib import Path

import pytest

from app.ingestion import pipeline
from app.ingestion.docling_parser import ParsedPage, pdf_raw_text
from app.ingestion.pdf_layout import SheetMap

ROOT = Path(__file__).resolve().parents[2]
SCHRIFTFELD = ROOT / "examples" / "schriftfeld"
VARIANTS = [
    "blatt_schraegstrich.pdf",
    "blatt_von.pdf",
    "bl_punkt.pdf",
    "sheet_of.pdf",
    "getrennte_felder.pdf",
    "eplan_seitenname.pdf",
]
TITLES = {
    3: "Einspeisung 400 V",
    4: "Steuerspannung 24 V DC",
    5: "Motorsteuerung Band",
    6: "Not-Halt-Kreis",
    7: "SPS-Eingaenge",
}
DB = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)
WS = "ws-pipeline-sheets-test"


def _docling_ohne_ocr(path: Path) -> list[ParsedPage]:
    return [
        ParsedPage(page=page, markdown="" if text.strip() else "<!-- image -->", raw_text=text)
        for page, text in pdf_raw_text(path).items()
    ]


@pytest.fixture
def ohne_docling(monkeypatch):
    monkeypatch.setattr(pipeline, "parse_document", _docling_ohne_ocr)
    monkeypatch.setattr(pipeline, "_set_progress", lambda *_args: None)


def _note(name: str, doc_type: str = "schematic") -> str:
    _pieces, _page_count, note = pipeline._build_pieces(
        "doc", SCHRIFTFELD / name, doc_type, vision=False
    )
    return note


def test_plan_ohne_blattnummer_meldet_die_annahme(ohne_docling):
    assert _note("ohne_blattnummer.pdf") == "Blatt-Map unsicher: Seite = Blatt angenommen"


def test_luecke_nennt_die_seite_ohne_blattnummer(ohne_docling):
    assert _note("luecke.pdf") == "Blatt-Map unsicher: Seite 5 ohne eindeutige Blattnummer"


@pytest.mark.parametrize("name", VARIANTS)
def test_gelesene_blatt_map_bleibt_ohne_hinweis(ohne_docling, name):
    assert _note(name) == ""


def test_hinweis_nur_fuer_stromlaufplaene(ohne_docling):
    assert _note("ohne_blattnummer.pdf", "manual") == ""


def test_hinweis_fasst_mehrere_seiten_zusammen():
    sheets = SheetMap(9, {1: 1, 5: 5}, {2: 2, 3: 3, 4: 4}, (2, 3, 4))
    expected = "Blatt-Map unsicher: Seiten 2–4 ohne eindeutige Blattnummer"
    assert pipeline.sheet_map_note(sheets) == expected
    assert pipeline.sheet_map_note(SheetMap(3, {1: 1, 2: 2, 3: 3})) == ""


def test_blatttitel_folgen_der_blattnummer_nicht_der_seite(ohne_docling):
    read = pipeline.document_pieces(SCHRIFTFELD / "blatt_von.pdf", "schematic")
    assert read.titles == TITLES
    front = {piece.page: piece.section for piece in read.pieces if piece.page in (1, 2)}
    assert front == {1: "", 2: ""}  # Deckblatt und Inhaltsverzeichnis ohne Blatttitel


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


def _in_workspace(action):
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            return action(session)
    finally:
        reset_workspace(token)


@pytest.fixture
def plaene(monkeypatch, tmp_path):
    """Zwei Schriftfeld-Fixtures als Uploads (Kopien) in einer Quelle des Test-Workspace; raeumt hinterher auf."""
    from app.config import get_settings
    from app.db import session_scope
    from app.models import Document, KnowledgeSource, Workspace

    dim = get_settings().embedding_dim

    class _NullEmbeddings:
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * dim for _ in texts]

    monkeypatch.setattr(pipeline, "parse_document", _docling_ohne_ocr)
    monkeypatch.setattr(pipeline, "embeddings", _NullEmbeddings())
    with session_scope() as session:
        session.merge(Workspace(id=WS, name=WS))
    _wipe_sources()

    def create(session):
        source = KnowledgeSource(name="Blatt-Map-Test")
        session.add(source)
        session.flush()
        ids = {}
        for name in ("blatt_von.pdf", "ohne_blattnummer.pdf"):
            upload = tmp_path / name
            shutil.copyfile(SCHRIFTFELD / name, upload)
            document = Document(
                source_id=source.id, filename=name, storage_path=str(upload), doc_type="schematic"
            )
            session.add(document)
            session.flush()
            ids[name] = document.id
        return source.id, ids

    yield _in_workspace(create)
    _wipe_sources()


@DB
def test_locate_findet_blatt_1_hinter_deckblatt_und_inhaltsverzeichnis(plaene):
    from app.api.sources import locate

    _source_id, ids = plaene
    found = _in_workspace(lambda session: locate(ids["blatt_von.pdf"], "/1.2", session))
    assert found.page == 3 and found.column == 2 and found.box is not None


@DB
def test_rueckfall_steht_am_dokument_und_im_zitat_resolver(plaene):
    from app.citations import check_answer
    from app.models import Document

    source_id, ids = plaene
    for document_id in ids.values():
        pipeline.ingest_document(document_id)
    progress = _in_workspace(
        lambda session: {name: session.get(Document, i).progress for name, i in ids.items()}
    )
    assert "Blatt-Map unsicher: Seite = Blatt angenommen" in progress["ohne_blattnummer.pdf"]
    assert "Blatt-Map" not in progress["blatt_von.pdf"]

    checks, _summary = _in_workspace(
        lambda session: check_answer(
            session,
            "-K1 [[blatt_von.pdf|/3.1]] und [[ohne_blattnummer.pdf|/3.1]].",
            [source_id],
            [{"filename": "blatt_von.pdf"}, {"filename": "ohne_blattnummer.pdf"}],
        )
    )
    assert (checks[0]["valid"], checks[0]["checked"]) == (True, True)
    assert (checks[1]["valid"], checks[1]["checked"], checks[1]["reason"]) == (
        True,
        False,
        "Nicht geprueft: Blatt-Map unsicher, Blatt 3 auf Seite 3 angenommen",
    )
