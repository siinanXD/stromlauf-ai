"""Scans erkennen statt still verlieren (Issue #64): Scan-Fixtures, Seiten ohne Text im Hinweis, Scan-Meldung.

Docling laeuft hier nicht, weil der Backend-Job der CI seine Modelle nicht hat. `_docling_ohne_ocr` bildet nach,
was parse_document ohne OCR liefert: Bildseiten nur "<!-- image -->", Textseiten ihren PDF-Rohtext. Gegen das
echte Docling am 2026-09-29 geprueft, fuer eine 200-dpi-Bildseite und fuer Festo-Handbuch Seite 83.
"""

import ctypes
import importlib.util
import io
import os
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
import pytest

from app.ingestion import pipeline
from app.ingestion.docling_parser import ParsedPage, pdf_raw_text
from app.ingestion.pipeline import Piece

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "examples" / "scan"
FULL = SCAN / "01_Stromlaufplan_FB-01_scan.pdf"
PARTIAL = SCAN / "01_Stromlaufplan_FB-01_teilscan.pdf"
SIDEWAYS = SCAN / "01_Stromlaufplan_FB-01_quer.pdf"
TEXT = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
DB = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)
WS = "ws-pipeline-scan-test"


def _docling_ohne_ocr(path: Path) -> list[ParsedPage]:
    return [
        ParsedPage(page=page, markdown="" if text.strip() else "<!-- image -->", raw_text=text)
        for page, text in pdf_raw_text(path).items()
    ]


@pytest.fixture
def ohne_docling(monkeypatch):
    monkeypatch.setattr(pipeline, "parse_document", _docling_ohne_ocr)
    monkeypatch.setattr(pipeline, "_set_progress", lambda *_args: None)


def _load_make_scan():
    path = ROOT / "scripts" / "example_docs" / "make_scan.py"
    spec = importlib.util.spec_from_file_location("make_scan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pdf_mit_leerer_textebene(path: Path) -> None:
    """Seite 1 mit lesbarem Text, Seite 2 nur mit Textobjekten ohne lesbare Zeichen (wie Festo-Handbuch S. 83)."""
    pdf = pdfium.PdfDocument.new()
    font = pdfium_c.FPDFText_LoadStandardFont(pdf.raw, b"Helvetica")
    for text in ("-K1 Schuetz Foerdermotor", "      "):
        page = pdf.new_page(595, 842)
        obj = pdfium_c.FPDFPageObj_CreateTextObj(pdf.raw, font, ctypes.c_float(12))
        buffer = ctypes.create_string_buffer((text + "\x00").encode("utf-16-le"))
        pdfium_c.FPDFText_SetText(obj, ctypes.cast(buffer, pdfium_c.FPDF_WIDESTRING))
        pdfium_c.FPDFPageObj_Transform(obj, 1, 0, 0, 1, 72, 700)
        pdfium_c.FPDFPage_InsertObject(page.raw, obj)
        pdfium_c.FPDFPage_GenerateContent(page.raw)
    pdf.save(str(path))
    pdf.close()


@pytest.mark.parametrize(
    ("path", "image_pages"),
    [(FULL, set(range(1, 8))), (PARTIAL, {3}), (SIDEWAYS, {4})],
    ids=["scan", "teilscan", "quer"],
)
def test_scan_fixtures_haben_textebene_nur_ausserhalb_der_bildseiten(path, image_pages):
    raw = pdf_raw_text(path)
    assert sorted(raw) == list(range(1, 8))
    assert {page for page, text in raw.items() if not text.strip()} == image_pages


def test_scan_fixtures_zusammen_unter_drei_mb_und_nur_blatt_4_liegt_hochkant():
    assert sum(p.stat().st_size for p in (FULL, PARTIAL, SIDEWAYS)) < 3 * 1024 * 1024
    pdf = pdfium.PdfDocument(str(SIDEWAYS))
    try:
        sizes = [pdf[index].get_size() for index in range(len(pdf))]
    finally:
        pdf.close()
    assert [index + 1 for index, (width, height) in enumerate(sizes) if height > width] == [4]


def test_make_scan_erzeugt_mit_festem_seed_dieselben_bytes():
    make_scan = _load_make_scan()
    first = make_scan.image_pdf([make_scan.scan_image(TEXT, 3)])
    assert first == make_scan.image_pdf([make_scan.scan_image(TEXT, 3)])
    assert first.startswith(b"%PDF")


def test_seitenlisten_werden_verdichtet():
    assert pipeline.page_ranges([2, 3, 4, 5, 7]) == "2–5, 7"
    assert pipeline.page_ranges([1, 3]) == "1, 3"
    assert pipeline.page_ranges([4]) == "4"
    assert pipeline.page_ranges([]) == ""


def test_teilscan_meldet_blatt_3_ohne_text_und_behaelt_die_anderen_seiten(ohne_docling):
    read = pipeline.document_pieces(PARTIAL, "schematic")
    assert read.page_count == 7 and read.empty_pages == [3]
    assert sorted({piece.page for piece in read.pieces}) == [1, 2, 4, 5, 6, 7]
    pieces, page_count, note = pipeline._build_pieces("doc", PARTIAL, "schematic", vision=False)
    assert page_count == 7 and note == "1 von 7 Seiten ohne Text: 3"


def test_text_pdf_bekommt_keinen_hinweis(ohne_docling):
    pieces, page_count, note = pipeline._build_pieces("doc", TEXT, "schematic", vision=False)
    assert page_count == 7 and note == "" and pieces


def test_voll_scan_scheitert_mit_seitenzahl_statt_mit_ocr_hinweis(ohne_docling):
    with pytest.raises(ValueError, match=r"^Scan ohne Textebene \(7 von 7 Seiten\)"):
        pipeline._build_pieces("doc", FULL, "schematic", vision=False)


def test_scan_meldung_unterscheidet_ob_die_texterkennung_lief():
    assert pipeline.scan_message(7, ocr_enabled=False) == (
        "Scan ohne Textebene (7 von 7 Seiten), Texterkennung noch nicht aktiv"
    )
    assert pipeline.scan_message(3, ocr_enabled=True) == (
        "Scan ohne Textebene (3 von 3 Seiten), auch die Texterkennung (OCR_ENABLED) fand keinen Text"
    )


def test_textobjekte_ohne_lesbare_zeichen_zaehlen_als_seite_ohne_text(ohne_docling, tmp_path):
    path = tmp_path / "handbuch.pdf"
    _pdf_mit_leerer_textebene(path)
    read = pipeline.document_pieces(path, "manual")
    assert read.empty_pages == [2] and [piece.page for piece in read.pieces] == [1]


def test_von_der_vision_beschriebene_bildseite_gilt_nicht_als_verloren(ohne_docling, monkeypatch):
    monkeypatch.setattr(pipeline, "vision_skip_note", lambda: "")
    monkeypatch.setattr(
        pipeline,
        "_vision_pieces",
        lambda *_args, **_kwargs: ([Piece("Vision: Schuetz -K1 auf Blatt 3", page=3)], [], []),
    )
    _, _, note = pipeline._build_pieces("doc", PARTIAL, "schematic", vision=True)
    assert note == ""


def test_langer_hinweis_passt_in_die_spalte_progress():
    long_note = "Vision-Analyse fehlgeschlagen auf Seiten " + ", ".join(map(str, range(1, 300, 2)))
    progress = pipeline.progress_text(512, 1024, long_note)
    assert len(progress) == 200 and progress.startswith("512 Abschnitte, 1024 Kennzeichen · Vision")
    assert progress.endswith("…")
    assert pipeline.progress_text(3, 5, "") == "3 Abschnitte, 5 Kennzeichen"


def test_detect_endpunkt_meldet_den_voll_scan():
    from fastapi import UploadFile

    from app.api.sources import detect_document_type

    found = detect_document_type(UploadFile(file=io.BytesIO(FULL.read_bytes()), filename=FULL.name))
    assert found.reason.startswith("Scan (keine Textebene)") and found.page_count == 7


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
def test_ingest_teilscan_wird_ready_mit_hinweis_und_voll_scan_failed_mit_seitenzahl(monkeypatch):
    from app.config import get_settings
    from app.db import session_scope
    from app.models import Document, KnowledgeSource, Workspace
    from app.tenancy import reset_workspace, set_workspace

    dim = get_settings().embedding_dim

    class _NullEmbeddings:
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * dim for _ in texts]

    monkeypatch.setattr(pipeline, "parse_document", _docling_ohne_ocr)
    monkeypatch.setattr(pipeline, "embeddings", _NullEmbeddings())
    with session_scope() as session:
        session.merge(Workspace(id=WS, name=WS))
    _wipe_sources()
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="Scan-Test")
            session.add(source)
            session.flush()
            ids = {}
            for key, path in (("teil", PARTIAL), ("voll", FULL)):
                document = Document(
                    source_id=source.id,
                    filename=path.name,
                    storage_path=str(path),
                    doc_type="schematic",
                )
                session.add(document)
                session.flush()
                ids[key] = document.id
    finally:
        reset_workspace(token)

    try:
        for document_id in ids.values():
            pipeline.ingest_document(document_id)
        token = set_workspace(WS)
        try:
            with session_scope() as session:
                partial = session.get(Document, ids["teil"])
                full = session.get(Document, ids["voll"])
                result = {
                    "teil": (partial.status, partial.progress, partial.error),
                    "voll": (full.status, full.progress, full.error),
                }
        finally:
            reset_workspace(token)
    finally:
        _wipe_sources()

    status, progress, error = result["teil"]
    assert (status, error) == ("ready", None)
    assert progress.endswith(" · 1 von 7 Seiten ohne Text: 3") and " Abschnitte, " in progress
    status, progress, error = result["voll"]
    assert status == "failed" and progress == ""
    assert (
        error == "ValueError: Scan ohne Textebene (7 von 7 Seiten), Texterkennung noch nicht aktiv"
    )
