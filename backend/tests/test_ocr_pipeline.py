"""OCR in der Pipeline (Issue #66): Modus, durchsuchbare Fassung neben dem Original, Bilder, Lesart je Seite.

Docling laeuft hier nicht (keine Modelle im Backend-Job der CI); `_docling_ohne_ocr` liest wie Docling die Textebene.
Die Texterkennung selbst ist echt (RapidOCR lokal). Tests, die in eine Upload-Datei schreiben, arbeiten auf Kopien.
"""

import os
import shutil
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image

from app.config import Settings
from app.ingestion import ocr, pipeline
from app.ingestion.docling_parser import ParsedPage, pdf_raw_text
from app.ingestion.tags import extract_tags

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "examples" / "scan" / "01_Stromlaufplan_FB-01_scan.pdf"
PARTIAL = ROOT / "examples" / "scan" / "01_Stromlaufplan_FB-01_teilscan.pdf"
TEXT = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
DB = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)


def _docling_ohne_ocr(path: Path) -> list[ParsedPage]:
    return [
        ParsedPage(page=page, markdown="" if text.strip() else "<!-- image -->", raw_text=text)
        for page, text in pdf_raw_text(path).items()
    ]


def _one_page(source: Path, page: int, target: Path) -> Path:
    """Einseitiges PDF aus einer Seite von source (schnell zu erkennen)."""
    pdf, single = pdfium.PdfDocument(str(source)), pdfium.PdfDocument.new()
    try:
        single.import_pages(pdf, [page - 1])
        single.save(str(target))
    finally:
        single.close()
        pdf.close()
    return target


def _tags(text: str) -> set[str]:
    return {tag.tag for tag in extract_tags(text)}


def test_ocr_modus_standard_auto_und_ocr_enabled_heisst_always():
    assert Settings(_env_file=None).effective_ocr_mode == "auto"
    assert Settings(_env_file=None, ocr_enabled=True).effective_ocr_mode == "always"
    assert Settings(_env_file=None, ocr_mode="off").effective_ocr_mode == "off"
    with pytest.raises(ValueError):
        Settings(_env_file=None, ocr_mode="manchmal")


def test_docling_macht_keine_eigene_ocr_mehr():
    """Scans liest app/ingestion/ocr.py; Doclings OCR (Standard: an) wuerde Torch-Modelle nachladen und doppelt
    erkennen. Das gilt auch mit OCR_ENABLED=true, das jetzt OCR_MODE=always heisst."""
    from app.ingestion import docling_parser

    assert docling_parser.pdf_pipeline_options().do_ocr is False


def test_originalpfad_und_dateien_eines_uploads(tmp_path):
    upload = tmp_path / "abc123.pdf"
    assert ocr.original_path(upload) == tmp_path / "abc123.orig.pdf"
    assert ocr.stored_files(upload) == [upload, tmp_path / "abc123.orig.pdf"]


def test_teilscan_wird_neben_dem_original_durchsuchbar_und_neu_verarbeiten_beginnt_beim_original(
    tmp_path,
):
    upload = tmp_path / "doc.pdf"
    shutil.copyfile(PARTIAL, upload)
    calls = []
    report = ocr.prepare_pdf(
        upload, "auto", progress=lambda page, total: calls.append((page, total))
    )
    original = ocr.original_path(upload)
    assert [page.page for page in report.pages] == [3] and calls == [(1, 1)]
    assert original.read_bytes() == PARTIAL.read_bytes()
    assert ocr.pages_without_text(upload) == []
    assert {"-K1", "-K2", "-M1"} <= _tags(pdf_raw_text(upload)[3])

    again = ocr.prepare_pdf(upload, "auto")  # Neu verarbeiten
    assert [page.page for page in again.pages] == [3]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["doc.orig.pdf", "doc.pdf"]

    assert (
        ocr.prepare_pdf(upload, "off") is None
    )  # ausgeschaltet: wieder das Original, ohne Textebene auf Blatt 3
    assert upload.read_bytes() == PARTIAL.read_bytes()


def test_text_pdf_braucht_keine_ocr_und_bekommt_kein_original(tmp_path):
    upload = tmp_path / "plan.pdf"
    shutil.copyfile(TEXT, upload)
    assert ocr.prepare_pdf(upload, "auto") is None
    assert not ocr.original_path(upload).exists() and upload.read_bytes() == TEXT.read_bytes()
    assert (
        ocr.prepare_pdf(tmp_path / "fehlt.pdf", "auto") is None
    )  # fehlende Datei meldet das Parsen


def test_hinweis_nennt_seiten_konfidenz_und_zeit():
    line = ocr.OcrLine("-K1", ((0, 0), (1, 0), (1, 1), (0, 1)), 0.9)
    pages = tuple(ocr.PageOcr(n, (line,), 200, 0, 0.0, 3.0) for n in (1, 2))
    assert (
        ocr.ocr_note(ocr.OcrReport(pages, 6.2)) == "2 Seiten per OCR, Ø Konfidenz 0,90, 3,1 s/Seite"
    )
    assert (
        ocr.ocr_note(ocr.OcrReport(pages[:1], 3.0))
        == "1 Seite per OCR, Ø Konfidenz 0,90, 3,0 s/Seite"
    )
    assert ocr.ocr_note(ocr.OcrReport((), 0.0)) == ""


def test_zeilen_in_lesereihenfolge():
    def line(text: str, x: float, y: float) -> ocr.OcrLine:
        return ocr.OcrLine(text, ((x, y), (x + 0.1, y), (x + 0.1, y + 0.02), (x, y + 0.02)), 0.9)

    lines = [line("rechts", 0.5, 0.101), line("unten", 0.1, 0.3), line("links", 0.1, 0.1)]
    assert ocr.lines_to_text(lines) == "links  rechts\nunten"


def test_bild_und_pdf_seite_liefern_dieselben_kennzeichen(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "parse_document", _docling_ohne_ocr)
    image, _ = ocr.render_page(SCAN, 3)
    png = tmp_path / "blatt3.png"
    image.save(png)
    from_image = pipeline.document_pieces(png, "schematic")
    assert from_image.page_count is None and [p.meta["read"] for p in from_image.pieces] == ["ocr"]

    upload = _one_page(SCAN, 3, tmp_path / "blatt3.pdf")
    ocr.prepare_pdf(upload, "auto")
    from_pdf = pipeline.document_pieces(upload, "schematic")
    image_tags = {row.tag for row in pipeline.tag_rows(from_image.pieces)}
    pdf_tags = {row.tag for row in pipeline.tag_rows(from_pdf.pieces)}
    assert image_tags == pdf_tags and {"-K1", "-K2", "-F2"} <= image_tags


def test_bild_ohne_ocr_liefert_keinen_text(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "get_settings", lambda: Settings(_env_file=None, ocr_mode="off"))
    png = tmp_path / "leer.png"
    Image.new("L", (200, 100), 255).save(png)
    assert pipeline.document_pieces(png, "manual").pieces == []


WS = "ws-ocr-pipeline-test"


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


@pytest.fixture
def teilscan_upload(monkeypatch, tmp_path):
    """Teil-Scan als Upload in tmp_path, Dokumentzeile im Test-Workspace; raeumt hinterher auf."""
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
    upload = tmp_path / "doc.pdf"
    shutil.copyfile(PARTIAL, upload)
    with session_scope() as session:
        session.merge(Workspace(id=WS, name=WS))
    _wipe_sources()
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="OCR-Pipeline-Test")
            session.add(source)
            session.flush()
            document = Document(
                source_id=source.id,
                filename=PARTIAL.name,
                storage_path=str(upload),
                doc_type="schematic",
            )
            session.add(document)
            session.flush()
            ids = (document.id, source.id)
    finally:
        reset_workspace(token)
    yield ids, upload
    _wipe_sources()


def _in_workspace(action):
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            return action(session)
    finally:
        reset_workspace(token)


@DB
def test_ingest_liest_die_bildseite_per_ocr_und_neu_verarbeiten_verdoppelt_nichts(teilscan_upload):
    from sqlalchemy import func, select

    from app.models import Chunk, Document

    (document_id, _), upload = teilscan_upload
    pipeline.ingest_document(document_id)

    def state(session):
        document = session.get(Document, document_id)
        chunks = session.scalars(select(Chunk).where(Chunk.document_id == document_id)).all()
        reading = {chunk.page: chunk.meta.get("read") for chunk in chunks}
        page_3 = next(chunk for chunk in chunks if chunk.page == 3)
        count = session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
        )
        return (
            document.status,
            document.progress,
            document.error,
            reading,
            page_3.meta,
            page_3.content,
            count,
        )

    status, progress, error, reading, meta_3, content_3, count = _in_workspace(state)
    assert (status, error) == ("ready", None)
    assert "1 Seite per OCR, Ø Konfidenz 0," in progress and "ohne Text" not in progress
    assert reading == {1: "text", 2: "text", 3: "ocr", 4: "text", 5: "text", 6: "text", 7: "text"}
    assert meta_3["ocr_conf"] > 0.8 and {"-K1", "-K2", "-M1"} <= _tags(content_3)

    pipeline.ingest_document(document_id)  # "Neu verarbeiten"
    assert _in_workspace(state)[-1] == count
    assert sorted(p.name for p in upload.parent.iterdir()) == ["doc.orig.pdf", "doc.pdf"]


@DB
def test_spalte_und_zitat_auf_der_ocr_seite(teilscan_upload):
    from app.api.sources import locate
    from app.citations import check_answer

    (document_id, source_id), _ = teilscan_upload
    pipeline.ingest_document(document_id)

    found = _in_workspace(lambda session: locate(document_id, "/3.4", session))
    assert found.page == 3 and found.column == 4 and found.box is not None
    checks, summary = _in_workspace(
        lambda session: check_answer(
            session,
            f"-K1 steht auf [[{PARTIAL.name}|/3.4]].",
            [source_id],
            [{"filename": PARTIAL.name}],
        )
    )
    assert checks[0]["valid"] and checks[0]["checked"]


@DB
def test_loeschen_entfernt_auch_das_original(teilscan_upload):
    from app.api.sources import delete_document

    (document_id, _), upload = teilscan_upload
    pipeline.ingest_document(document_id)
    assert ocr.original_path(upload).exists()
    _in_workspace(lambda session: delete_document(document_id, session))
    assert list(upload.parent.iterdir()) == []


def test_scan_meldung_nennt_den_modus():
    assert pipeline.scan_message(7, "off") == (
        "Scan ohne Textebene (7 von 7 Seiten), Texterkennung ausgeschaltet (OCR_MODE=off)"
    )
    assert pipeline.scan_message(3, "auto") == (
        "Scan ohne Textebene (3 von 3 Seiten), auch die Texterkennung fand keinen Text"
    )
