import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.ingestion.docling_parser import DOCLING_SUFFIXES, PLAIN_TEXT_SUFFIXES
from app.ingestion.pdf_layout import page_columns, parse_ref, sheet_page
from app.ingestion.pipeline import detect_doc_type, ingest_document
from app.ingestion.vision import render_page_png
from app.models import DocStatus, DocType, Document, KnowledgeSource
from app.schemas import DocumentOut, LocateBox, LocateOut, SourceCreate, SourceOut

router = APIRouter(prefix="/api", tags=["sources"])

ALLOWED_SUFFIXES = DOCLING_SUFFIXES | PLAIN_TEXT_SUFFIXES | {".awl", ".sdf"}


def _get_source(session: Session, source_id: str) -> KnowledgeSource:
    source = session.get(KnowledgeSource, source_id)
    if source is None:
        raise HTTPException(404, "Wissensquelle nicht gefunden")
    return source


def _get_document(session: Session, document_id: str) -> Document:
    document = session.get(Document, document_id)
    if document is None:
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

    resolved_type = detect_doc_type(filename, doc_type)
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
