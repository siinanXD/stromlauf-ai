"""`meta`-Event am Ende eines Chat-Streams: referenzierte Bauteile, Zitate, Belege - deterministisch,
ohne weiteren Modellaufruf (docs/product/ux-spec.md §3.2, Issue #27).

- referenced_tags: Betriebsmittel aus dem Antworttext, die im Kennzeichen-Index der Quelle vorkommen
- citations: die Fundstellen der Werkzeugaufrufe (dedupliziert)
- evidence: Seiten der Zitate (fuer Belegbilder) und Hotspots in Schaltschrankfotos der Maschine
- citation_checks / citations_valid: jeder Beleg [[Datei|Ort]] der Antwort, gegen Fundstellen und Index
  geprueft (app/citations.py, Issue #46)

Fuer die Antwortbloecke der Stoerfall-Arbeitsflaeche (Spec 2026-10-01-stoerfall-arbeitsflaeche-design.md, Abschnitt 2):

- part_kinds: Art je referenziertem Kennzeichen in der Lesart seiner Quelle, wie im Maschinenmodell
- signal_start: erstes referenziertes Kennzeichen mit Signalweg, sonst None
- plan_spots: je Kennzeichen die erste Stelle im Stromlaufplan mit Blatt, Blatttitel und Spalte, hoechstens 4
"""

from __future__ import annotations

import contextvars
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.signal import graph_for_source
from app.citations import check_answer
from app.db import session_scope
from app.ingestion.letter_codes import OFFEN, detect_edition, kind_of
from app.ingestion.page_titles import is_parts_list
from app.ingestion.pdf_layout import sheet_map
from app.ingestion.signal_graph import signal_path
from app.ingestion.tag_columns import tag_columns
from app.ingestion.tags import extract_tags
from app.models import DocType, Document, Machine, TagOccurrence, TagType

logger = logging.getLogger(__name__)

MAX_TAGS = 12
MAX_PAGE_EVIDENCE = 4
MAX_HOTSPOT_EVIDENCE = 6
MAX_PLAN_SPOTS = 4
# Der Signalweg-Graph liegt nach dem ersten Aufbau im Cache; der erste Aufbau einer grossen Quelle (Planleser ueber
# alle Seiten) darf das Ende der Antwort nicht aufhalten.
SIGNAL_START_TIMEOUT_S = 2.0
_signal_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="signal-start")


def tags_in_answer(text: str, known: set[str]) -> list[str]:
    """Betriebsmittel im Antworttext, Reihenfolge des ersten Vorkommens, nur bekannte Kennzeichen."""
    seen: list[str] = []
    for tag in extract_tags(text):
        if tag.tag_type == TagType.DEVICE and tag.tag in known and tag.tag not in seen:
            seen.append(tag.tag)
    return seen[:MAX_TAGS]


def page_evidence(citations: list[dict]) -> list[dict]:
    """Seitenbelege aus den Fundstellen (nur PDF-Seiten, erste je Dokument+Seite)."""
    out: list[dict] = []
    for ref in citations:
        page = ref.get("page")
        if not page or not str(ref.get("filename", "")).lower().endswith(".pdf"):
            continue
        out.append(
            {
                "kind": "page",
                "document_id": ref["document_id"],
                "filename": ref.get("filename", ""),
                "doc_type": ref.get("doc_type", ""),
                "page": page,
                "label": f"{ref.get('filename', '')} S. {page}",
            }
        )
        if len(out) >= MAX_PAGE_EVIDENCE:
            break
    return out


def hotspot_evidence(machine: Machine | None, tags: list[str]) -> list[dict]:
    if machine is None or not tags:
        return []
    wanted = {t.upper() for t in tags}
    out: list[dict] = []
    for cabinet in machine.cabinets:
        for hotspot in cabinet.hotspots:
            if hotspot.tag and hotspot.tag.upper() in wanted:
                out.append(
                    {
                        "kind": "cabinet",
                        "cabinet_id": cabinet.id,
                        "cabinet_title": cabinet.title,
                        "hotspot_id": hotspot.id,
                        "tag": hotspot.tag,
                        "label": hotspot.label,
                        "box": {"x": hotspot.x, "y": hotspot.y, "w": hotspot.w, "h": hotspot.h},
                        "confirmed": hotspot.confirmed,
                    }
                )
                if len(out) >= MAX_HOTSPOT_EVIDENCE:
                    return out
    return out


def known_device_tags(session: Session, source_ids: list[str]) -> set[str]:
    """Betriebsmittel im Kennzeichen-Index der Quellen; leere Liste = alle Quellen des Workspace (wie die Werkzeuge)."""
    query = select(TagOccurrence.tag).where(TagOccurrence.tag_type == TagType.DEVICE).distinct()
    if source_ids:
        query = query.where(TagOccurrence.source_id.in_(source_ids))
    return set(session.scalars(query))


def device_tags_by_source(session: Session, source_ids: list[str]) -> dict[str, set[str]]:
    """Betriebsmittel je Quelle, Scope wie known_device_tags; die Vereinigung ist known_device_tags."""
    query = (
        select(TagOccurrence.source_id, TagOccurrence.tag)
        .where(TagOccurrence.tag_type == TagType.DEVICE)
        .distinct()
    )
    if source_ids:
        query = query.where(TagOccurrence.source_id.in_(source_ids))
    by_source: dict[str, set[str]] = {}
    for source_id, tag in session.execute(query):
        by_source.setdefault(source_id, set()).add(tag)
    return by_source


# --- part_kinds -------------------------------------------------------------------------------


def part_kinds(
    tags: list[str], by_source: dict[str, set[str]], extra: dict[str, list[str]] | None = None
) -> dict[str, str]:
    """Art je Kennzeichen, leer, wenn der Kennbuchstabe in der Lesart nichts Sicheres sagt (Issue #99).

    Die Lesart bestimmt detect_edition je Quelle aus allen ihren Betriebsmitteln und den Teilen der Draufsicht
    ihrer Maschine (extra), genau wie das Maschinenmodell (ingestion/machine_map.build_map). Steht ein Kennzeichen
    in mehreren Quellen, gilt die erste nach ID."""
    editions: dict[str, str] = {}

    def edition_of(source_id: str) -> str:
        if source_id not in editions:
            tags_of = by_source[source_id] | set((extra or {}).get(source_id, []))
            editions[source_id] = detect_edition(sorted(tags_of)).name
        return editions[source_id]

    kinds: dict[str, str] = {}
    for tag in tags:
        source_id = next((s for s in sorted(by_source) if tag in by_source[s]), None)
        kinds[tag] = kind_of(tag, edition_of(source_id) if source_id else OFFEN)
    return kinds


def _layout_tags(machine: Machine | None) -> dict[str, list[str]]:
    if machine is None or not machine.source_id or machine.layout is None:
        return {}
    return {machine.source_id: [part.tag for part in machine.layout.parts if part.tag]}


# --- signal_start -----------------------------------------------------------------------------


def _first_traceable(source_id: str, tags: list[str]) -> str | None:
    # eigene Session: der Aufruf darf den Zeitdeckel ueberdauern, ohne die Session der Antwort zu teilen
    with session_scope() as session:
        graph, _schematic = graph_for_source(session, source_id)
    return next((tag for tag in tags if signal_path(graph, tag) is not None), None)


def signal_start(
    tags: list[str], source_ids: list[str], timeout_s: float = SIGNAL_START_TIMEOUT_S
) -> str | None:
    """Erstes Kennzeichen, fuer das der Signalweg-Graph der Quelle einen Weg kennt; None sonst.

    Nur bei genau einer Quelle (Chat einer Maschine): der Block laedt den Weg ueber diese Quelle. Ein Fehler beim
    Aufbau des Graphen oder ein Aufbau ueber timeout_s ergibt None statt einer haengenden oder abgebrochenen Antwort;
    der Aufbau laeuft dann im Hintergrund zu Ende und liegt beim naechsten Mal im Cache."""
    if not tags or len(source_ids) != 1:
        return None
    # Kontext mitnehmen: der Workspace des Requests filtert auch die Abfragen im Hilfsthread
    context = contextvars.copy_context()
    future = _signal_pool.submit(context.run, _first_traceable, source_ids[0], list(tags))
    try:
        return future.result(timeout=timeout_s)
    except TimeoutError:
        logger.warning(
            "Signalweg-Start: Graph nach %.1f s noch nicht fertig, Block ohne Weg", timeout_s
        )
    except Exception:  # noqa: BLE001 - der Signalweg ist ein Zusatz, die Antwort darf daran nicht scheitern
        logger.warning("Signalweg-Start fehlgeschlagen", exc_info=True)
    return None


# --- plan_spots -------------------------------------------------------------------------------


# Blatttitel von Deckblatt und Inhaltsverzeichnis (Titel aus Inhaltsverzeichnis oder Schriftfeld, page_titles)
COVER_TITLE = re.compile(
    r"^\W*(deckblatt|titelblatt|inhaltsverzeichnis|inhalt\b|table of contents|contents\b|sommaire|cover)",
    re.I,
)


@dataclass(frozen=True)
class PlanRow:
    """Fundstelle eines Betriebsmittels auf einer Seite eines Stromlaufplans."""

    tag: str
    page: int
    section: str
    document_id: str
    filename: str
    storage_path: str


def plan_rows(session: Session, tags: list[str], source_ids: list[str]) -> list[PlanRow]:
    """Fundstellen der Kennzeichen in Stromlaufplaenen, je Dokument nach Seite; leerer Scope = alle Quellen."""
    if not tags:
        return []
    query = (
        select(
            TagOccurrence.tag,
            TagOccurrence.page,
            TagOccurrence.section,
            Document.id,
            Document.filename,
            Document.storage_path,
        )
        .join(Document, TagOccurrence.document_id == Document.id)
        .where(
            TagOccurrence.tag.in_(tags),
            TagOccurrence.tag_type == TagType.DEVICE,
            TagOccurrence.page.is_not(None),
            Document.doc_type == DocType.SCHEMATIC,
        )
        .order_by(Document.filename, Document.id, TagOccurrence.page, TagOccurrence.id)
    )
    if source_ids:
        query = query.where(TagOccurrence.source_id.in_(source_ids))
    return [PlanRow(*row) for row in session.execute(query)]


def first_plan_rows(tags: list[str], rows: list[PlanRow]) -> list[PlanRow]:
    """Je Kennzeichen die erste Fundstelle in einer PDF, in der Reihenfolge der Antwort, hoechstens MAX_PLAN_SPOTS.
    Stuecklisten-, Deckblatt- und Inhaltsseiten im Plan zaehlen nicht: dort steht das Teil in einer Liste, nicht an
    seiner Stelle im Plan."""
    first: dict[str, PlanRow] = {}
    for row in rows:
        if (
            row.tag not in first
            and Path(row.storage_path).suffix.lower() == ".pdf"
            and not is_parts_list(row.section)
            and not COVER_TITLE.match(row.section or "")
        ):
            first[row.tag] = row
    return [first[tag] for tag in tags if tag in first][:MAX_PLAN_SPOTS]


def plan_spot(row: PlanRow) -> dict:
    """Stelle im Plan mit Blatt aus dem Schriftfeld (nur gelesen, nie angenommen) und Spalte der Kopfzeile."""
    path = Path(row.storage_path)
    sheet = column = None
    try:
        sheet = sheet_map(path).read.get(row.page)
        column = tag_columns(path, row.page).get(row.tag)
    except (
        OSError,
        RuntimeError,
    ):  # Datei fehlt oder unlesbar (PdfiumError): ohne Blatt und Spalte
        logger.info("Planstelle ohne Blatt/Spalte: %s S. %s nicht lesbar", row.filename, row.page)
    return {
        "tag": row.tag,
        "document_id": row.document_id,
        "filename": row.filename,
        "page": row.page,
        "sheet": sheet,
        "title": row.section or "",
        "column": column,
    }


def build_meta(
    session: Session,
    *,
    answer: str,
    citations: list[dict],
    source_ids: list[str],
    machine_id: str | None,
) -> dict:
    by_source = device_tags_by_source(session, source_ids)
    tags = tags_in_answer(answer, set().union(*by_source.values()))
    machine = session.get(Machine, machine_id) if machine_id else None
    checks, valid = check_answer(session, answer, source_ids, citations)
    spots = first_plan_rows(tags, plan_rows(session, tags, source_ids))
    return {
        "referenced_tags": tags,
        "citations": citations,
        "evidence": [*hotspot_evidence(machine, tags), *page_evidence(citations)],
        "citation_checks": checks,
        "citations_valid": valid,
        "part_kinds": part_kinds(tags, by_source, _layout_tags(machine)),
        "signal_start": signal_start(tags, source_ids),
        "plan_spots": [plan_spot(row) for row in spots],
    }
