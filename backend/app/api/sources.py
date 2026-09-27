import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.ingestion import doctype
from app.ingestion.docling_parser import DOCLING_SUFFIXES, PLAIN_TEXT_SUFFIXES
from app.ingestion.pdf_layout import known_sheets, page_columns, parse_ref, sheet_page
from app.ingestion.pipeline import detect_doc_type, ingest_document
from app.ingestion.profile import CORE_DOC_TYPES, Occurrence, build_profile
from app.ingestion.vision import render_page_png
from app.models import DocStatus, DocType, Document, KnowledgeSource, TagOccurrence
from app.schemas import (
    DocTypeDetection,
    DocumentOut,
    LocateBox,
    LocateOut,
    ProfileDocType,
    ProfileDocument,
    SourceCreate,
    SourceOut,
    SourceProfile,
)
from app.tenancy import same_workspace

router = APIRouter(prefix="/api", tags=["sources"])

ALLOWED_SUFFIXES = DOCLING_SUFFIXES | PLAIN_TEXT_SUFFIXES | {".awl", ".sdf"}


def _get_source(session: Session, source_id: str) -> KnowledgeSource:
    source = session.get(KnowledgeSource, source_id)
    if source is None or not same_workspace(source):
        raise HTTPException(404, "Wissensquelle nicht gefunden")
    return source


def _get_document(session: Session, document_id: str) -> Document:
    document = session.get(Document, document_id)
    if document is None or not same_workspace(document):
        raise HTTPException(404, "Dokument nicht gefunden")
    return document


@router.get("/sources", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_session)):
    rows = session.execute(
        select(KnowledgeSource, func.count(Document.id))
        .outerjoin(Document)
        .group_by(KnowledgeSource.id)
        .order_by(KnowledgeSource.name)
    ).all()
    return [
        SourceOut.model_validate(source).model_copy(update={"document_count": count})
        for source, count in rows
    ]


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(body: SourceCreate, session: Session = Depends(get_session)):
    source = KnowledgeSource(name=body.name.strip(), description=body.description.strip())
    session.add(source)
    session.commit()
    return SourceOut.model_validate(source)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str, session: Session = Depends(get_session)):
    source = _get_source(session, source_id)
    paths = [Path(d.storage_path) for d in source.documents]
    session.delete(source)
    session.commit()
    for path in paths:
        path.unlink(missing_ok=True)


@router.get("/sources/{source_id}/documents", response_model=list[DocumentOut])
def list_documents(source_id: str, session: Session = Depends(get_session)):
    _get_source(session, source_id)
    return session.scalars(
        select(Document).where(Document.source_id == source_id).order_by(Document.created_at)
    ).all()


@router.get("/sources/{source_id}/profile", response_model=SourceProfile)
def source_profile(source_id: str, session: Session = Depends(get_session)):
    """Steckbrief: welche Dokumenttypen da sind, wie die Kennzeichen sie abdecken, wo Luecken sind."""
    source = _get_source(session, source_id)
    documents = session.scalars(
        select(Document).where(Document.source_id == source_id).order_by(Document.doc_type, Document.filename)
    ).all()
    doc_type_of = {d.id: d.doc_type for d in documents}
    tag_counts: dict[str, int] = dict(
        session.execute(
            select(TagOccurrence.document_id, func.count())
            .where(TagOccurrence.source_id == source_id)
            .group_by(TagOccurrence.document_id)
        ).all()
    )
    rows = session.execute(
        select(TagOccurrence.tag, TagOccurrence.tag_type, TagOccurrence.document_id, TagOccurrence.page).where(
            TagOccurrence.source_id == source_id
        )
    ).all()
    occurrences = [Occurrence(tag, tag_type, doc_type_of[doc_id], doc_id, page) for tag, tag_type, doc_id, page in rows]
    ready = [d for d in documents if d.status == DocStatus.READY]
    present = {d.doc_type for d in ready}
    sheets: set[int] | None = None
    for document in ready:
        path = Path(document.storage_path)
        if document.doc_type == DocType.SCHEMATIC and path.suffix.lower() == ".pdf" and path.exists():
            sheets = (sheets or set()) | known_sheets(path)
    profile = build_profile(occurrences, present, sheets)
    return SourceProfile(
        source_id=source.id,
        source_name=source.name,
        documents=[
            ProfileDocument(
                id=d.id, filename=d.filename, doc_type=d.doc_type, status=d.status, page_count=d.page_count,
                tag_count=tag_counts.get(d.id, 0),
            )
            for d in documents
        ],
        doc_types=[
            ProfileDocType(
                doc_type=doc_type,
                present=doc_type in present,
                filenames=[d.filename for d in ready if d.doc_type == doc_type],
            )
            for doc_type in CORE_DOC_TYPES
        ],
        sheets=sorted(sheets or []),
        **profile,
    )


@router.post("/sources/{source_id}/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    source_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: DocType = Form(DocType.AUTO),
    vision: bool = Form(False),
    session: Session = Depends(get_session),
):
    _get_source(session, source_id)
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            415, f"Dateityp {suffix or '(ohne)'} nicht unterstuetzt. Erlaubt: {sorted(ALLOWED_SUFFIXES)}"
        )

    document_id = uuid.uuid4().hex
    path = get_settings().upload_dir / f"{document_id}{suffix}"
    with path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    resolved_type = detect_doc_type(filename, doc_type, path)
    document = Document(
        id=document_id,
        source_id=source_id,
        filename=filename,
        storage_path=str(path),
        doc_type=resolved_type,
        vision_enrichment=vision and suffix == ".pdf",
    )
    session.add(document)
    session.commit()
    background.add_task(ingest_document, document_id)
    return document


@router.post("/documents/detect", response_model=DocTypeDetection)
def detect_document_type(file: UploadFile = File(...)):
    """Dokumenttyp aus dem Inhalt vorschlagen, ohne zu speichern (Upload-Dialog, Bestaetigung durch den Nutzer)."""
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, f"Dateityp {suffix or '(ohne)'} nicht unterstuetzt. Erlaubt: {sorted(ALLOWED_SUFFIXES)}")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        shutil.copyfileobj(file.file, handle)
        temp_path = Path(handle.name)
    try:
        found = doctype.detect(filename, temp_path)
        page_count = _pdf_page_count(temp_path) if suffix == ".pdf" else None
    finally:
        temp_path.unlink(missing_ok=True)
    return DocTypeDetection(filename=filename, page_count=page_count, **found.__dict__)


def _pdf_page_count(path: Path) -> int | None:
    """Seitenzahl fuer die Kostenschaetzung; None, wenn die Datei kein lesbares PDF ist."""
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        return None


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, session: Session = Depends(get_session)):
    return _get_document(session, document_id)


@router.post("/documents/{document_id}/reingest", response_model=DocumentOut)
def reingest_document(
    document_id: str, background: BackgroundTasks, session: Session = Depends(get_session)
):
    document = _get_document(session, document_id)
    if document.status == DocStatus.PROCESSING:
        raise HTTPException(409, "Dokument wird gerade verarbeitet")
    document.status = DocStatus.PENDING
    document.attempts = 0  # bewusster Neustart: Zaehler der Neustart-Sperre zuruecksetzen
    session.commit()
    background.add_task(ingest_document, document_id)
    return document


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, session: Session = Depends(get_session)):
    document = _get_document(session, document_id)
    path = Path(document.storage_path)
    session.delete(document)
    session.commit()
    path.unlink(missing_ok=True)


@router.get("/documents/{document_id}/pages/{page}/image")
def page_image(document_id: str, page: int, session: Session = Depends(get_session)):
    document = _get_document(session, document_id)
    path = Path(document.storage_path)
    if path.suffix.lower() != ".pdf":
        raise HTTPException(400, "Nur PDF-Dokumente haben Seitenbilder")
    try:
        png = render_page_png(path, page, max_edge=2400)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@router.get("/documents/{document_id}/locate", response_model=LocateOut)
def locate(document_id: str, ref: str, session: Session = Depends(get_session)):
    """Beleg wie '/3.8' oder 'S. 12' auf Seite und Spaltenmarkierung abbilden."""
    document = _get_document(session, document_id)
    path = Path(document.storage_path)
    if path.suffix.lower() != ".pdf":
        raise HTTPException(400, "Nur PDF-Dokumente haben Seiten")
    sheet, column, page = parse_ref(ref)
    if sheet is not None:
        page = sheet_page(path, sheet) or page
        if page is None:
            raise HTTPException(404, f"Blatt {sheet} nicht gefunden")
    if page is None:
        raise HTTPException(400, f"Verweis '{ref}' nennt weder Blatt noch Seite")
    if column is None:
        return LocateOut(page=page)
    hit = next((c for c in page_columns(path, page) if c.n == column), None)
    if hit is None:
        return LocateOut(page=page, column=column)
    return LocateOut(page=page, column=column, box=LocateBox(x0=hit.x0, y0=hit.y0, x1=hit.x1, y1=hit.y1))
