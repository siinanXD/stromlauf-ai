"""Ingestion: Datei -> Textstuecke -> Embeddings + Kennzeichen-Index."""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete

from app import ledger
from app.config import get_settings
from app.db import session_scope
from app.embeddings import embeddings
from app.ingestion import awl_parser, doctype, ocr
from app.ingestion.docling_parser import ParsedPage, parse_document
from app.ingestion.page_titles import page_titles
from app.ingestion.tags import detect_folio_style, extract_tags
from app.ingestion.vision import describe_page
from app.llm import missing_key
from app.models import Chunk, DocStatus, DocType, Document, TagOccurrence, TagType
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


@dataclass(frozen=True)
class TagRow:
    """Eine Zeile des Kennzeichen-Index: je Kennzeichen, Typ, Seite und Abschnitt einmal."""

    tag: str
    tag_type: TagType
    page: int | None
    section: str
    context: str


@dataclass
class DocumentPieces:
    """Gelesene Stuecke eines Dokuments, ohne Vision und ohne Datenbank.

    Grundlage fuer den Upload (`_build_pieces`) und den Ingest-Benchmark (`eval/run_ingest.py`), damit
    beide dieselbe Lesekette messen. `parsed` und `titles` braucht nur die Vision-Analyse.
    """

    pieces: list[Piece]
    page_count: int | None = None
    parsed: list[ParsedPage] = field(default_factory=list)
    titles: dict[int, str] = field(default_factory=dict)
    # Seiten ohne lesbaren Text (Bildseite, Scan, Textobjekte ohne Zeichen); frueher still verworfen (Issue #64)
    empty_pages: list[int] = field(default_factory=list)


PROGRESS_MAX = 200  # Laenge der Spalte documents.progress


def page_ranges(pages: list[int]) -> str:
    """[2, 3, 4, 5, 7] -> "2–5, 7"."""
    runs: list[list[int]] = []
    for page in sorted(pages):
        if runs and page == runs[-1][-1] + 1:
            runs[-1].append(page)
        else:
            runs.append([page])
    return ", ".join(f"{run[0]}–{run[-1]}" if len(run) > 1 else str(run[0]) for run in runs)


def empty_pages_note(pages: list[int], page_count: int | None) -> str:
    """Hinweis fuer das Dokument, z. B. "1 von 7 Seiten ohne Text: 3"; leer, wenn keine Seite fehlt."""
    return f"{len(pages)} von {page_count} Seiten ohne Text: {page_ranges(pages)}" if pages else ""


def scan_message(page_count: int, mode: str) -> str:
    """Fehlertext fuer ein PDF, in dem keine einzige Seite lesbaren Text hat, auch nach der Texterkennung."""
    scan = f"Scan ohne Textebene ({page_count} von {page_count} Seiten)"
    if mode == "off":
        return f"{scan}, Texterkennung ausgeschaltet (OCR_MODE=off)"
    return f"{scan}, auch die Texterkennung fand keinen Text"


def progress_text(chunks: int, tags: int, note: str) -> str:
    """Abschlusstext am Dokument: Zaehler, dann Hinweise; passt immer in die Spalte."""
    text = " · ".join(part for part in (f"{chunks} Abschnitte, {tags} Kennzeichen", note) if part)
    return text if len(text) <= PROGRESS_MAX else text[: PROGRESS_MAX - 1] + "…"


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


def split_pieces(pieces: list[Piece]) -> list[Piece]:
    """Zu lange Stuecke auf Chunk-Groesse teilen; Seite, Abschnitt und Lesemodus bleiben erhalten."""
    return [part for piece in pieces for part in _split(piece)]


def tag_rows(pieces: list[Piece]) -> list[TagRow]:
    """Kennzeichen aller Stuecke, je (Kennzeichen, Typ, Seite, Abschnitt) einmal; der erste Fund liefert den Kontext."""
    rows: list[TagRow] = []
    seen: set[tuple] = set()
    for piece in pieces:
        for tag in extract_tags(
            piece.content, plc_loose=piece.plc_loose, folio_style=piece.folio_style
        ):
            key = (tag.tag, tag.tag_type, piece.page, piece.section)
            if key in seen:
                continue
            seen.add(key)
            rows.append(TagRow(tag.tag, tag.tag_type, piece.page, piece.section, tag.context))
    return rows


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


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _image_pieces(path: Path) -> list[Piece]:
    """Bild (Foto, Scan als Bilddatei): Text per OCR statt Docling, ein Stueck je Bild bzw. TIFF-Seite (Issue #66)."""
    if get_settings().effective_ocr_mode == "off":
        return []
    frames = ocr.read_image(path)
    pieces = []
    for number, (text, confidence) in enumerate(frames, start=1):
        if not text.strip():
            continue
        meta = {
            "read": "ocr",
            **({"ocr_conf": round(confidence, 3)} if confidence is not None else {}),
        }
        pieces.append(
            Piece(
                text,
                section=f"Seite {number}" if len(frames) > 1 else "",
                meta=meta,
                folio_style=detect_folio_style(text),
            )
        )
    return pieces


def document_pieces(
    path: Path, doc_type: str, progress: Callable[[str], None] | None = None
) -> DocumentPieces:
    """Stuecke eines Dokuments ohne Vision und ohne Datenbank; `progress` meldet den Docling-Schritt."""
    # .scl (TIA-Quelle) laeuft durch denselben Bausteinparser: ein Chunk je Baustein, ohne Netzwerke
    if doc_type == DocType.PLC_PROGRAM or path.suffix.lower() in {".awl", ".scl"}:
        return DocumentPieces(_awl_pieces(path))
    if doc_type == DocType.PLC_SYMBOLS or path.suffix.lower() == ".sdf":
        return DocumentPieces(_symbol_pieces(path))
    if path.suffix.lower() in IMAGE_SUFFIXES:
        if progress:
            progress("Texterkennung")
        return DocumentPieces(_image_pieces(path))

    if progress:
        progress("Docling-Analyse")
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
    empty_pages = [p.page for p in parsed if p.page and not p.text.strip()]
    return DocumentPieces(pieces, page_count, parsed, titles, empty_pages)


def _build_pieces(
    document_id: str, path: Path, doc_type: str, vision: bool, machine_id: str | None = None
) -> tuple[list[Piece], int | None, str]:
    """Liefert (Stuecke, Seitenzahl, Hinweis).

    Seiten ohne lesbaren Text, die auch die Vision-Analyse nicht beschrieben hat, stehen im Hinweis. Hat
    keine einzige Seite eines PDFs Text, bricht die Verarbeitung mit der Seitenzahl ab (Issue #64).
    """
    read = document_pieces(path, doc_type, progress=lambda text: _set_progress(document_id, text))
    pieces, page_count = list(read.pieces), read.page_count

    note = ""
    # Nur Dokumente, die Docling gelesen hat, haben Seiten fuer die Vision-Analyse (nicht AWL/SCL/SDF)
    if vision and read.parsed and path.suffix.lower() == ".pdf":
        note = vision_skip_note()
        if not note:
            page_texts = {p.page: p.raw_text or p.markdown for p in read.parsed if p.page}
            vision_pieces, failed, skipped = _vision_pieces(
                document_id, path, page_texts, machine_id, read.titles
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

    covered = {piece.page for piece in pieces}
    lost = [page for page in read.empty_pages if page not in covered]
    if page_count and len(lost) == page_count:
        raise ValueError(scan_message(page_count, get_settings().effective_ocr_mode))
    note = " · ".join(part for part in (note, empty_pages_note(lost, page_count)) if part)
    return pieces, page_count, note


def _prepare_scan(document_id: str, path: Path, doc_type: str) -> tuple[ocr.OcrReport | None, str]:
    """PDF-Upload per OCR durchsuchbar machen (Issue #66). Scheitert die Erkennung, laeuft die Ingestion mit der
    vorhandenen Textebene weiter und nennt den Fehler am Dokument."""
    if path.suffix.lower() != ".pdf" or doc_type in {DocType.PLC_PROGRAM, DocType.PLC_SYMBOLS}:
        return None, ""
    try:
        report = ocr.prepare_pdf(
            path,
            get_settings().effective_ocr_mode,
            progress=lambda page, total: _set_progress(document_id, f"OCR Seite {page}/{total}"),
        )
    except Exception as exc:
        logger.exception("Texterkennung fehlgeschlagen: %s", path.name)
        return None, f"Texterkennung fehlgeschlagen: {type(exc).__name__}"
    return report, ""


def _mark_reading(pieces: list[Piece], report: ocr.OcrReport | None, path: Path) -> None:
    """Lesart je PDF-Seite in Chunk.meta: "ocr" mit Konfidenz oder "text" (Textebene des Originals)."""
    if path.suffix.lower() != ".pdf":
        return
    confidence = {page.page: page.confidence for page in report.pages} if report else {}
    for piece in pieces:
        if piece.page is None or "read" in piece.meta or piece.kind == "vision":
            continue
        if piece.page in confidence:
            piece.meta["read"] = "ocr"
            if confidence[piece.page] is not None:
                piece.meta["ocr_conf"] = round(confidence[piece.page], 3)
        else:
            piece.meta["read"] = "text"


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
        ocr_report, ocr_problem = _prepare_scan(document_id, path, doc_type)
        raw_pieces, page_count, note = _build_pieces(
            document_id, path, doc_type, vision, machine_id
        )
        _mark_reading(raw_pieces, ocr_report, path)
        note = " · ".join(
            part
            for part in (ocr.ocr_note(ocr_report) if ocr_report else "", ocr_problem, note)
            if part
        )
        pieces = split_pieces(raw_pieces)
        if not pieces:  # reine Scan-PDFs meldet schon _build_pieces mit Seitenzahl
            raise ValueError("Kein Text im Dokument gefunden")

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
            # dieselbe Funktion misst eval/run_ingest.py gegen die Ground Truth
            rows = tag_rows(pieces)
            for row in rows:
                session.add(
                    TagOccurrence(
                        document_id=document_id,
                        source_id=source_id,
                        tag=row.tag,
                        tag_type=row.tag_type,
                        page=row.page,
                        section=row.section,
                        context=row.context,
                    )
                )

            document = session.get(Document, document_id)
            document.status = DocStatus.READY
            document.page_count = page_count
            document.progress = progress_text(len(pieces), len(rows), note)
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
