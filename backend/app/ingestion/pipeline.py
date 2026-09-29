"""Ingestion: Datei -> Textstuecke -> Embeddings + Kennzeichen-Index."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete

from app import ledger
from app.config import get_settings
from app.db import session_scope
from app.embeddings import embeddings
from app.ingestion import awl_parser, doctype
from app.ingestion.docling_parser import parse_document
from app.ingestion.page_titles import page_titles
from app.ingestion.tags import detect_folio_style, extract_tags
from app.ingestion.vision import describe_page
from app.llm import missing_key
from app.models import Chunk, DocStatus, DocType, Document, TagOccurrence
from app.tenancy import reset_workspace, set_workspace
from app.tracing import vision_trace

logger = logging.getLogger(__name__)

_EMBED_BATCH = 64

# Docling und das Embedding-Modell brauchen je Lauf mehrere GB RAM. Mehrere Uploads
# gleichzeitig (z. B. per Skript) laufen deshalb nacheinander statt parallel.
_INGEST_LOCK = threading.Lock()


@dataclass
class Piece:
    content: str
    kind: str = "text"
    page: int | None = None
    section: str = ""
    meta: dict = field(default_factory=dict)
    plc_loose: bool = False  # "A 1.0" mit Leerzeichen als SPS-Adresse werten
    folio_style: bool = False  # Kennzeichen ohne Minus im Blatt-Stil (4Q1, 9K1) werten, siehe tags.detect_folio_style


def detect_doc_type(filename: str, requested: str, path: Path | None = None) -> DocType:
    """Gewuenschter Typ, sonst Erkennung aus Inhalt (mit path) und Dateiname (ingestion/doctype.py)."""
    if requested and requested != DocType.AUTO:
        return DocType(requested)
    return doctype.detect(filename, path).doc_type


def _splitter() -> RecursiveCharacterTextSplitter:
    settings = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )


def _split(piece: Piece) -> list[Piece]:
    if len(piece.content) <= get_settings().chunk_size:
        return [piece]
    return [
        Piece(
            part,
            piece.kind,
            piece.page,
            piece.section,
            dict(piece.meta),
            piece.plc_loose,
            piece.folio_style,
        )
        for part in _splitter().split_text(piece.content)
    ]


def _set_progress(document_id: str, progress: str) -> None:
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document:
            document.progress = progress


def _budget_exhausted() -> bool:
    with session_scope() as session:
        try:
            ledger.check_budget(session)
        except ledger.BudgetExceeded:
            return True
    return False


def _book_page(machine_id: str | None, usage: ledger.Usage | None) -> None:
    """Seitenanalyse sofort zubuchen (auch wenn die Ingestion danach scheitert, war der Aufruf teuer)."""
    if usage is None:
        return
    with session_scope() as session:
        ledger.record_usage(session, usage, purpose="vision.page", machine_id=machine_id, images=1)


def _awl_pieces(path: Path) -> list[Piece]:
    blocks = awl_parser.parse_awl(awl_parser.read_text(path))
    if not blocks:
        raise ValueError(
            "Keine AWL-Bausteine gefunden (erwartet z.B. FUNCTION_BLOCK ... END_FUNCTION_BLOCK)"
        )
    pieces = []
    for block in blocks:
        if block.declaration:
            pieces.append(
                Piece(
                    f"Baustein {block.label}\nDeklaration:\n{block.declaration}",
                    kind="awl_block",
                    section=block.label,
                    meta={"block": block.label},
                    plc_loose=True,
                )
            )
        for network in block.networks:
            if not network.code and not network.title:
                continue
            pieces.append(
                Piece(
                    f"Baustein {block.label}\nNetzwerk {network.number}: {network.title}\n{network.code}",
                    kind="awl_network",
                    section=f"{block.label} / NW {network.number} {network.title}".strip(),
                    meta={"block": block.label, "network": network.number},
                    plc_loose=True,
                )
            )
    return pieces


def _symbol_pieces(path: Path) -> list[Piece]:
    rows = awl_parser.parse_symbol_table(awl_parser.read_text(path))
    if not rows:
        raise ValueError("Symboltabelle enthaelt keine Zeilen")
    lines = [f"{r['symbol']} | {r['address']} | {r['data_type']} | {r['comment']}" for r in rows]
    header = "Symbol | Adresse | Datentyp | Kommentar"
    return [
        Piece(
            header + "\n" + "\n".join(lines[i : i + 40]),
            kind="symbols",
            section="Symboltabelle",
            plc_loose=True,
        )
        for i in range(0, len(lines), 40)
    ]


def _vision_pieces(
    document_id: str,
    path: Path,
    pages: dict[int, str],
    machine_id: str | None = None,
    titles: dict[int, str] | None = None,
) -> tuple[list[Piece], list[int], list[int]]:
    """Liefert (Stuecke, fehlgeschlagene Seiten, wegen Monatslimit uebersprungene Seiten)."""
    settings = get_settings()
    pieces: list[Piece] = []
    failed: list[int] = []
    skipped: list[int] = []
    done = 0
    # ein Trace je Dokument, alle Seiten als Aufrufe darin
    trace = vision_trace(document_id, "seitenanalyse")

    def work(page: int) -> tuple[int, str | None, ledger.Usage | None]:
        config, collector = ledger.collect(trace)
        try:
            return page, describe_page(path, page, pages[page], config), collector.total()
        except Exception:
            logger.exception("Vision-Analyse fehlgeschlagen: %s Seite %s", path.name, page)
            return page, None, collector.total()

    ordered = sorted(pages)
    batch_size = max(1, settings.vision_concurrency)
    with ThreadPoolExecutor(max_workers=batch_size) as pool:
        for start in range(0, len(ordered), batch_size):
            # Limit vor jedem Schub pruefen (im Hauptthread, der den Workspace-Kontext hat)
            if _budget_exhausted():
                skipped = ordered[start:]
                break
            for page, description, usage in pool.map(work, ordered[start : start + batch_size]):
                done += 1
                _book_page(machine_id, usage)
                _set_progress(document_id, f"Vision-Analyse {done}/{len(pages)}")
                if description is None:
                    failed.append(page)
                elif description.strip():
                    pieces.append(
                        Piece(
                            description,
                            kind="vision",
                            page=page,
                            section=(titles or {}).get(page, "Vision-Analyse"),
                        )
                    )
    return pieces, failed, skipped


def vision_skip_note() -> str:
    """Hinweis, wenn der Schluessel des Providers von VISION_MODEL fehlt; leer, wenn die Analyse laufen kann."""
    settings = get_settings()
    try:
        missing = missing_key(settings.vision_model, settings)
    except ValueError as exc:
        return f"Vision-Analyse uebersprungen: {exc}"
    return f"Vision-Analyse uebersprungen: {missing} fehlt" if missing else ""


def _build_pieces(
    document_id: str, path: Path, doc_type: str, vision: bool, machine_id: str | None = None
) -> tuple[list[Piece], int | None, str]:
    """Liefert (Stuecke, Seitenzahl, Hinweis)."""
    # .scl (TIA-Quelle) laeuft durch denselben Bausteinparser: ein Chunk je Baustein, ohne Netzwerke
    if doc_type == DocType.PLC_PROGRAM or path.suffix.lower() in {".awl", ".scl"}:
        return _awl_pieces(path), None, ""
    if doc_type == DocType.PLC_SYMBOLS or path.suffix.lower() == ".sdf":
        return _symbol_pieces(path), None, ""

    _set_progress(document_id, "Docling-Analyse")
    parsed = parse_document(path)
    # Blatttitel als Abschnitt, Stuecklistenseiten als kind "bom", Kennzeichen-Stil je Dokument (Issue #39)
    titles, parts_pages = page_titles(parsed)
    folio = detect_folio_style("\n".join(p.raw_text or p.markdown for p in parsed))
    pieces = [
        Piece(
            p.text,
            kind="bom" if p.page in parts_pages else "text",
            page=p.page,
            section=titles.get(p.page, "") if p.page else "",
            folio_style=folio,
        )
        for p in parsed
        if p.text.strip()
    ]
    page_count = max((p.page for p in parsed if p.page), default=None)

    note = ""
    if vision and path.suffix.lower() == ".pdf":
        note = vision_skip_note()
        if not note:
            page_texts = {p.page: p.raw_text or p.markdown for p in parsed if p.page}
            vision_pieces, failed, skipped = _vision_pieces(
                document_id, path, page_texts, machine_id, titles
            )
            pieces += vision_pieces
            notes = []
            if failed:
                notes.append(
                    f"Vision-Analyse fehlgeschlagen auf Seiten {', '.join(map(str, failed))}"
                )
            if skipped:
                notes.append(
                    f"Vision-Analyse ab Seite {skipped[0]} uebersprungen: KI-Monatslimit erreicht"
                )
            note = "; ".join(notes)
    return pieces, page_count, note


def ingest_document(document_id: str) -> None:
    """Hintergrundjob. Schreibt Status/Fehler ans Dokument, wirft nicht."""
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        document.status = DocStatus.PROCESSING
        document.error = None
        document.attempts = (document.attempts or 0) + 1
        path = Path(document.storage_path)
        filename, source_id = document.filename, document.source_id
        doc_type, vision = document.doc_type, document.vision_enrichment
        workspace_id = document.workspace_id
        machine_id = ledger.machine_for_source(session, source_id)  # fuers Kostenbuch
    # Chunks und Kennzeichen gehoeren zum Workspace des Dokuments (auch im Resume-Thread ohne Request)
    workspace_token = set_workspace(workspace_id)

    if not _INGEST_LOCK.acquire(blocking=False):
        _set_progress(document_id, "wartet, anderes Dokument wird gerade verarbeitet")
        _INGEST_LOCK.acquire()
    try:
        raw_pieces, page_count, note = _build_pieces(
            document_id, path, doc_type, vision, machine_id
        )
        pieces = [part for piece in raw_pieces for part in _split(piece)]
        if not pieces:
            raise ValueError(
                "Kein Text im Dokument gefunden (gescanntes PDF? OCR_ENABLED=true setzen)"
            )

        vectors: list[list[float]] = []
        for start in range(0, len(pieces), _EMBED_BATCH):
            _set_progress(document_id, f"Embeddings {start}/{len(pieces)}")
            batch = pieces[start : start + _EMBED_BATCH]
            vectors += embeddings.embed_documents(
                [_embedding_text(filename, piece) for piece in batch]
            )

        with session_scope() as session:
            # Re-Ingestion: alte Eintraege ersetzen
            session.execute(delete(Chunk).where(Chunk.document_id == document_id))
            session.execute(delete(TagOccurrence).where(TagOccurrence.document_id == document_id))

            seen_tags: set[tuple] = set()
            for seq, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
                session.add(
                    Chunk(
                        document_id=document_id,
                        source_id=source_id,
                        page=piece.page,
                        kind=piece.kind,
                        section=piece.section,
                        content=piece.content,
                        meta={**piece.meta, "seq": seq},
                        embedding=vector,
                    )
                )
                for tag in extract_tags(
                    piece.content, plc_loose=piece.plc_loose, folio_style=piece.folio_style
                ):
                    key = (tag.tag, tag.tag_type, piece.page, piece.section)
                    if key in seen_tags:
                        continue
                    seen_tags.add(key)
                    session.add(
                        TagOccurrence(
                            document_id=document_id,
                            source_id=source_id,
                            tag=tag.tag,
                            tag_type=tag.tag_type,
                            page=piece.page,
                            section=piece.section,
                            context=tag.context,
                        )
                    )

            document = session.get(Document, document_id)
            document.status = DocStatus.READY
            document.page_count = page_count
            document.progress = note or f"{len(pieces)} Abschnitte, {len(seen_tags)} Kennzeichen"
    except Exception as exc:
        logger.exception("Ingestion fehlgeschlagen: %s", filename)
        with session_scope() as session:
            document = session.get(Document, document_id)
            if document:
                document.status = DocStatus.FAILED
                document.error = f"{type(exc).__name__}: {exc}"
                document.progress = ""
    finally:
        _INGEST_LOCK.release()
        reset_workspace(workspace_token)


def _embedding_text(filename: str, piece: Piece) -> str:
    header = filename
    if piece.page:
        header += f" | Seite {piece.page}"
    if piece.section:
        header += f" | {piece.section}"
    return f"{header}\n{piece.content}"
