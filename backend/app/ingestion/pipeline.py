"""Ingestion: Datei -> Textstuecke -> Embeddings + Kennzeichen-Index."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete

from app.config import get_settings
from app.db import session_scope
from app.embeddings import embeddings
from app.ingestion import awl_parser
from app.ingestion.docling_parser import parse_document
from app.ingestion.tags import extract_tags
from app.ingestion.vision import describe_page
from app.models import Chunk, DocStatus, DocType, Document, TagOccurrence

logger = logging.getLogger(__name__)

_FILENAME_HINTS: list[tuple[str, DocType]] = [
    (r"st(ü|ue|u)ckliste|\bbom\b|artikelliste", DocType.BOM),
    (r"klemm", DocType.TERMINAL_PLAN),
    (r"stromlauf|schaltplan|eplan|schematic|elektroplan", DocType.SCHEMATIC),
    (r"handbuch|manual|anleitung|betriebsanl|datasheet|datenblatt", DocType.MANUAL),
]
_EMBED_BATCH = 64


@dataclass
class Piece:
    content: str
    kind: str = "text"
    page: int | None = None
    section: str = ""
    meta: dict = field(default_factory=dict)
    plc_loose: bool = False  # "A 1.0" mit Leerzeichen als SPS-Adresse werten


def detect_doc_type(filename: str, requested: str) -> DocType:
    if requested and requested != DocType.AUTO:
        return DocType(requested)
    suffix = Path(filename).suffix.lower()
    if suffix == ".awl":
        return DocType.PLC_PROGRAM
    if suffix == ".sdf":
        return DocType.PLC_SYMBOLS
    lowered = filename.lower()
    for pattern, doc_type in _FILENAME_HINTS:
        if re.search(pattern, lowered):
            return doc_type
    return DocType.OTHER


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
        Piece(part, piece.kind, piece.page, piece.section, dict(piece.meta), piece.plc_loose)
        for part in _splitter().split_text(piece.content)
    ]


def _set_progress(document_id: str, progress: str) -> None:
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document:
            document.progress = progress


def _awl_pieces(path: Path) -> list[Piece]:
    blocks = awl_parser.parse_awl(awl_parser.read_text(path))
    if not blocks:
        raise ValueError("Keine AWL-Bausteine gefunden (erwartet z.B. FUNCTION_BLOCK ... END_FUNCTION_BLOCK)")
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


def _vision_pieces(document_id: str, path: Path, pages: dict[int, str]) -> tuple[list[Piece], list[int]]:
    settings = get_settings()
    pieces: list[Piece] = []
    failed: list[int] = []
    done = 0

    def work(page: int) -> tuple[int, str | None]:
        try:
            return page, describe_page(path, page, pages[page])
        except Exception:
            logger.exception("Vision-Analyse fehlgeschlagen: %s Seite %s", path.name, page)
            return page, None

    with ThreadPoolExecutor(max_workers=settings.vision_concurrency) as pool:
        for page, description in pool.map(work, sorted(pages)):
            done += 1
            _set_progress(document_id, f"Vision-Analyse {done}/{len(pages)}")
            if description is None:
                failed.append(page)
            elif description.strip():
                pieces.append(
                    Piece(description, kind="vision", page=page, section="Vision-Analyse")
                )
    return pieces, failed


def _build_pieces(document_id: str, path: Path, doc_type: str, vision: bool) -> tuple[list[Piece], int | None, str]:
    """Liefert (Stuecke, Seitenzahl, Hinweis)."""
    if doc_type == DocType.PLC_PROGRAM or path.suffix.lower() == ".awl":
        return _awl_pieces(path), None, ""
    if doc_type == DocType.PLC_SYMBOLS or path.suffix.lower() == ".sdf":
        return _symbol_pieces(path), None, ""

    _set_progress(document_id, "Docling-Analyse")
    parsed = parse_document(path)
    pieces = [Piece(p.text, page=p.page) for p in parsed if p.text.strip()]
    page_count = max((p.page for p in parsed if p.page), default=None)

    note = ""
    if vision and path.suffix.lower() == ".pdf":
        if not get_settings().anthropic_api_key:
            note = "Vision-Analyse uebersprungen: ANTHROPIC_API_KEY fehlt"
        else:
            page_texts = {p.page: p.raw_text or p.markdown for p in parsed if p.page}
            vision_pieces, failed = _vision_pieces(document_id, path, page_texts)
            pieces += vision_pieces
            if failed:
                note = f"Vision-Analyse fehlgeschlagen auf Seiten {', '.join(map(str, failed))}"
    return pieces, page_count, note


def ingest_document(document_id: str) -> None:
    """Hintergrundjob. Schreibt Status/Fehler ans Dokument, wirft nicht."""
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        document.status = DocStatus.PROCESSING
        document.error = None
        path = Path(document.storage_path)
        filename, source_id = document.filename, document.source_id
        doc_type, vision = document.doc_type, document.vision_enrichment

    try:
        raw_pieces, page_count, note = _build_pieces(document_id, path, doc_type, vision)
        pieces = [part for piece in raw_pieces for part in _split(piece)]
        if not pieces:
            raise ValueError("Kein Text im Dokument gefunden (gescanntes PDF? OCR_ENABLED=true setzen)")

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
            for piece, vector in zip(pieces, vectors, strict=True):
                session.add(
                    Chunk(
                        document_id=document_id,
                        source_id=source_id,
                        page=piece.page,
                        kind=piece.kind,
                        section=piece.section,
                        content=piece.content,
                        meta=piece.meta,
                        embedding=vector,
                    )
                )
                for tag in extract_tags(piece.content, plc_loose=piece.plc_loose):
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


def _embedding_text(filename: str, piece: Piece) -> str:
    header = filename
    if piece.page:
        header += f" | Seite {piece.page}"
    if piece.section:
        header += f" | {piece.section}"
    return f"{header}\n{piece.content}"
