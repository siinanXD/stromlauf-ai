"""Zitat-Resolver: Belege ``[[Datei|Ort]]`` einer Antwort deterministisch pruefen (Issue #46).

Ein Beleg ist gueltig, wenn die Datei zu den Fundstellen der Werkzeugaufrufe gehoert UND der Ort in
dieser Datei existiert: ``S. n``/``Seite n`` auf einer Seite, ``/Blatt.Spalte``, ``/Blatt`` oder
``Blatt n`` auf einem Blatt des Plans (Schriftfeld), ein Kennzeichen (``-K1``, ``-X3:3``, ``A 4.0``,
``/3.2``) im Kennzeichen-Index der Datei, sonst ein Abschnitt (AWL-Baustein/Netzwerk, Symboltabelle)
in den Chunk-Abschnitten. Was sich nicht pruefen laesst (Dokument ohne Seiten, Index oder Abschnitte,
unlesbare PDF), gilt als gueltig, aber ``checked=False``. Kein Modellaufruf; die Kennzahl
``zitate_gueltig`` im Eval beruht hierauf.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion.pdf_layout import parse_ref, sheet_page
from app.ingestion.tags import extract_tags
from app.models import Chunk, DocStatus, Document, TagOccurrence, TagType

MARKER = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
MAX_MARKERS = 200  # mehr Belege je Antwort werden nicht mehr geprueft (Deckel gegen Missbrauch)

_FILLER = {"kap", "kapitel", "abschnitt", "seite", "s", "nr", "blatt", "bl"}
_WORD = re.compile(r"[a-z0-9]+")
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_LETTER_DIGIT = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_UNPLAUSIBLE = re.compile(r"\d{7,}")
_PAGE_WORD = re.compile(r"(?<![\w/])(?:S\.|Seite)\s*(\d{1,5})\b", re.I)
_SHEET_WORD = re.compile(r"\b(?:Blatt|Bl\.)\s*(\d{1,4})\b", re.I)
_BARE_SHEET = re.compile(r"/(\d{1,4})")  # "/7": Blatt ohne Spalte
_BLOCK = re.compile(r"\b(OB|FB|FC|DB|UDT|SFB|SFC)\s*(\d{1,5})\b", re.I)  # AWL-Baustein
_NETWORK = re.compile(r"\bNW\s*(\d{1,4}(?:/\d{1,4})*)\b", re.I)  # "NW 4", "NW 2/3"
_ALTERNATIVES = re.compile(r"\b\d+(?:/\d+)+\b")  # "2/3": eines von mehreren


@dataclass(frozen=True)
class DocIndex:
    """Was der Resolver ueber eine Datei der Wissensquelle weiss."""

    filename: str
    is_pdf: bool
    path: Path | None = None
    pages: frozenset[int] = frozenset()
    page_count: int | None = None
    tags: frozenset[str] = frozenset()
    sections: tuple[str, ...] = ()


@dataclass
class CitationCheck:
    text: str
    file: str
    locator: str
    valid: bool
    checked: bool
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _iter_markers(text: str) -> Iterator[tuple[str, str, str, str]]:
    """(Marker, Datei, Ort, zitierende Zeile) je Beleg, Reihenfolge des ersten Vorkommens, gleiche Belege einmal.

    Die zitierende Zeile ist der Text vor dem Marker ab dem letzten Zeilenumbruch bzw. vorigen Beleg.
    """
    seen: set[tuple[str, str]] = set()
    line_start = 0
    for match in MARKER.finditer(text):
        before = text[line_start : match.start()]
        context = before[before.rfind("\n") + 1 :]
        line_start = match.end()
        file, locator = match.group(1).strip(), match.group(2).strip()
        if (file, locator) in seen:
            continue
        seen.add((file, locator))
        yield match.group(0), file, locator, context


def parse_markers(text: str) -> list[tuple[str, str, str]]:
    """(Marker, Datei, Ort) je Beleg, Reihenfolge des ersten Vorkommens, gleiche Belege einmal."""
    return [(marker, file, locator) for marker, file, locator, _context in _iter_markers(text)]


def _stem(name: str) -> str:
    return name.rsplit(".", 1)[0].lower() if "." in name else name.lower()


def _find_docs(file: str, docs: Iterable[DocIndex]) -> list[DocIndex]:
    """Alle Dateien mit diesem Namen: genau, ohne Gross/Klein, sonst ueber den Stamm ohne Endung."""
    docs = list(docs)
    exact = [d for d in docs if d.filename == file]
    if exact:
        return exact
    lowered = [d for d in docs if d.filename.lower() == file.lower()]
    if lowered:
        return lowered
    return [d for d in docs if _stem(d.filename) == _stem(file)]


def _normalize(text: str) -> str:
    text = text.lower().translate(_UMLAUTS)
    return _LETTER_DIGIT.sub(" ", text)


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(_normalize(text)) if t not in _FILLER}


def _tag_stem(tag: str) -> str:
    """Betriebsmittel ohne Klemmennummer: ``-X3:3`` -> ``-X3``."""
    return tag.split(":")[0].upper()


def _tag_of(locator: str) -> tuple[str, str, bool] | None:
    """(Kennzeichen, Typ, macht es den ganzen Ort aus) fuer das laengste Kennzeichen im Ort, sonst None."""
    found = extract_tags(locator, plc_loose=True)
    if not found:
        return None
    compact = locator.upper().replace(" ", "")
    for tag in found:
        if tag.tag.upper().replace(" ", "") == compact:
            return tag.tag, tag.tag_type, True
    longest = max(found, key=lambda t: len(t.tag))
    return longest.tag, longest.tag_type, False


def _device_tags(context: str) -> list[str]:
    """Betriebsmittel und Klemmen der zitierenden Zeile, Reihenfolge des Vorkommens, je Geraet einmal."""
    out: list[str] = []
    for tag in extract_tags(context):
        if tag.tag_type in (TagType.DEVICE, TagType.TERMINAL) and _tag_stem(tag.tag) not in out:
            out.append(_tag_stem(tag.tag))
    return out


def _structure(text: str) -> tuple[set[tuple[str, str]], set[str], str]:
    """AWL-Bausteine (Art, Nummer), Netzwerknummern (Alternativen aufgeloest) und der Rest des Texts."""
    blocks = {(kind.upper(), nr) for kind, nr in _BLOCK.findall(text)}
    networks = {nr for group in _NETWORK.findall(text) for nr in group.split("/")}
    rest = _NETWORK.sub(" ", _BLOCK.sub(" ", text))
    return blocks, networks, rest


def _section_matches(locator: str, sections: Iterable[str]) -> bool:
    """Baustein und Netzwerk muessen zum Abschnitt passen, die uebrigen Woerter darin vorkommen.

    ``FB 10 NW 4 Stoerung`` verlangt Baustein FB 10, Netzwerk 4 und das Wort ``stoerung``; ``NW 2/3``
    laesst Netzwerk 2 oder 3 gelten. Ein Ort ohne Baustein/Netzwerk wird nur ueber seine Woerter geprueft.
    """
    blocks, networks, rest = _structure(locator)
    for tag in extract_tags(rest, plc_loose=True):
        rest = rest.replace(tag.tag, " ")
    alternatives = [set(group.split("/")) for group in _ALTERNATIVES.findall(rest)]
    base = _tokens(_ALTERNATIVES.sub(" ", rest))
    for section in sections:
        sec_blocks, sec_networks, _ = _structure(section)
        have = _tokens(section)
        if not blocks <= sec_blocks:
            continue
        if networks and not networks & sec_networks:
            continue
        if base <= have and all(choice & have for choice in alternatives):
            return True
    return False


def _check_doc(
    text: str,
    file: str,
    locator: str,
    doc: DocIndex,
    context: str,
    sheet_lookup: Callable[[Path, int], int | None],
) -> CitationCheck:
    invalid = lambda reason: CitationCheck(text, file, locator, False, True, reason)  # noqa: E731
    unverified = lambda reason: CitationCheck(text, file, locator, True, False, reason)  # noqa: E731
    ok = CitationCheck(text, file, locator, True, True)

    sheet, _column, page = parse_ref(locator)
    if page is None and (word := _PAGE_WORD.search(locator)):
        page = int(word.group(1))
    if page is not None:
        if page in doc.pages or (doc.page_count and 1 <= page <= doc.page_count):
            return ok
        if not doc.pages and not doc.page_count:
            return invalid(f"{doc.filename} hat keine Seiten")
        count = doc.page_count or max(doc.pages)
        return invalid(f"Seite {page} nicht in {doc.filename} ({count} Seiten)")

    if sheet is None:
        if bare := _BARE_SHEET.fullmatch(locator):
            sheet = int(bare.group(1))
        elif word := _SHEET_WORD.search(locator):
            sheet = int(word.group(1))
    if sheet is not None and doc.is_pdf and doc.path is not None:
        try:
            found = sheet_lookup(doc.path, sheet)
        except (OSError, RuntimeError):  # fehlende Datei, pypdfium2.PdfiumError (RuntimeError)
            return unverified(f"Ort nicht pruefbar: {doc.filename} nicht lesbar")
        return ok if found is not None else invalid(f"Blatt {sheet} nicht in {doc.filename}")

    known = {t.upper() for t in doc.tags}
    found = _tag_of(locator)
    if found is not None and found[2]:
        tag, tag_type, _whole = found
        if not known:
            return unverified(f"Ort nicht pruefbar: {doc.filename} hat keinen Kennzeichen-Index")
        if tag.upper() not in known:
            return invalid(f"Kennzeichen {tag} nicht in {doc.filename}")
        # Hinweis nur fuer Betriebsmittel: Klemmen (-X3:1) und Querverweise (/3.5) belegen naturgemaess
        # Aussagen ueber andere Geraete
        named = _device_tags(context)
        if tag_type == TagType.DEVICE and named and _tag_stem(tag) not in named:
            ok.reason = f"Satz nennt {', '.join(named)}, Beleg zeigt auf {tag}"
        return ok
    if locator.upper().replace(" ", "") in known:  # z. B. Blatt-Stil ohne Minus (4Q1)
        return ok

    if doc.sections:
        return (
            ok
            if _section_matches(locator, doc.sections)
            else invalid(f"Abschnitt '{locator}' nicht in {doc.filename}")
        )
    if found is not None:
        tag = found[0]
        if not known:
            return unverified(f"Ort nicht pruefbar: {doc.filename} hat keinen Kennzeichen-Index")
        return ok if tag.upper() in known else invalid(f"Kennzeichen {tag} nicht in {doc.filename}")
    return unverified(f"Ort nicht pruefbar: {doc.filename} hat keine Abschnitte")


def _check_one(
    text: str,
    file: str,
    locator: str,
    docs: list[DocIndex],
    cited: set[str] | None,
    sheet_lookup: Callable[[Path, int], int | None],
    context: str = "",
) -> CitationCheck:
    invalid = lambda reason: CitationCheck(text, file, locator, False, True, reason)  # noqa: E731

    if _UNPLAUSIBLE.search(locator):
        return invalid("Ortsangabe unplausibel")
    if not _tokens(locator) and not extract_tags(locator, plc_loose=True):
        return invalid("Ortsangabe fehlt")
    candidates = _find_docs(file, docs)
    if not candidates:
        return invalid("Datei nicht in der Wissensquelle")
    if cited is not None and candidates[0].filename.lower() not in cited:
        return invalid("Datei nicht in den Fundstellen der Antwort")

    # Gleicher Dateiname in mehreren Quellen: gueltig, sobald eine Datei den Ort bestaetigt;
    # sonst die Begruendung der umfangreichsten Datei (meiste Seiten)
    results = [_check_doc(text, file, locator, doc, context, sheet_lookup) for doc in candidates]
    for result in results:
        if result.valid and result.checked:
            return result
    for result in results:
        if result.valid:
            return result
    return max(zip(candidates, results, strict=True), key=lambda pair: pair[0].page_count or 0)[1]


def check_citations(
    answer: str,
    docs: Iterable[DocIndex],
    cited: Iterable[str] | None,
    sheet_lookup: Callable[[Path, int], int | None] = sheet_page,
) -> list[CitationCheck]:
    """Alle Belege einer Antwort pruefen.

    ``docs``: Dateien der Wissensquelle mit Seiten, Index und Abschnitten. ``cited``: Dateinamen der
    Fundstellen aus den Werkzeugaufrufen (None = jede Datei der Quelle zaehlt als Fundstelle).
    """
    doc_list = list(docs)
    cited_set = {c.lower() for c in cited} if cited is not None else None
    checks: list[CitationCheck] = []
    for index, (text, file, locator, context) in enumerate(_iter_markers(answer)):
        if index >= MAX_MARKERS:
            checks.append(
                CitationCheck(
                    text,
                    file,
                    locator,
                    True,
                    False,
                    f"Nicht geprueft: mehr als {MAX_MARKERS} Belege",
                )
            )
            continue
        checks.append(_check_one(text, file, locator, doc_list, cited_set, sheet_lookup, context))
    return checks


def summary(checks: Iterable[CitationCheck]) -> dict:
    """{"valid", "checked", "total"} fuer meta.citations_valid und den Eval."""
    items = list(checks)
    return {
        "valid": sum(c.valid for c in items),
        "checked": sum(c.checked for c in items),
        "total": len(items),
    }


def load_docs(
    session: Session, source_ids: list[str], filenames: Iterable[str] | None = None
) -> list[DocIndex]:
    """Index je fertiger Datei der Quellen: Seiten und Abschnitte aus den Chunks, Kennzeichen aus dem Index.

    ``source_ids`` leer = alle Quellen des Workspace (so suchen auch die Agenten-Werkzeuge ohne Scope).
    ``filenames`` (Gross/Klein egal, mit oder ohne Endung) begrenzt auf die zitierten Dateien; None laedt
    alle Dateien der Quellen. Die Mandantentrennung greift ueber die ORM-Filter: fremde Quellen liefern
    keine Dokumente.
    """
    query = select(Document).where(Document.status == DocStatus.READY)
    if source_ids:
        query = query.where(Document.source_id.in_(source_ids))
    if filenames is not None:
        wanted = {f.lower() for f in filenames}
        if not wanted:
            return []
        stems = {_stem(f) for f in wanted}
        without_suffix = func.lower(func.regexp_replace(Document.filename, r"\.[^.]*$", ""))
        query = query.where(func.lower(Document.filename).in_(wanted) | without_suffix.in_(stems))
    docs: list[DocIndex] = []
    for doc in session.scalars(query.order_by(Document.created_at.desc())):
        pages = session.scalars(
            select(Chunk.page)
            .where(Chunk.document_id == doc.id, Chunk.page.is_not(None))
            .distinct()
        )
        sections = session.scalars(
            select(Chunk.section).where(Chunk.document_id == doc.id).distinct()
        )
        tags = session.scalars(
            select(TagOccurrence.tag).where(TagOccurrence.document_id == doc.id).distinct()
        )
        docs.append(
            DocIndex(
                filename=doc.filename,
                is_pdf=doc.filename.lower().endswith(".pdf"),
                path=Path(doc.storage_path) if doc.storage_path else None,
                pages=frozenset(pages),
                page_count=doc.page_count,
                tags=frozenset(tags),
                sections=tuple(s for s in sections if s),
            )
        )
    return docs


def check_answer(
    session: Session, answer: str, source_ids: list[str], refs: list[dict] | None
) -> tuple[list[dict], dict]:
    """Belege einer Antwort gegen die Quellen pruefen: (citation_checks, citations_valid).

    ``refs`` sind die Fundstellen der Werkzeugaufrufe (Dicts mit ``filename``); None = jede Datei der Quellen gilt.
    """
    markers = parse_markers(answer)
    docs = load_docs(session, source_ids, {file for _, file, _ in markers}) if markers else []
    cited = {str(r.get("filename", "")) for r in refs} if refs is not None else None
    checks = check_citations(answer, docs, cited)
    return [c.as_dict() for c in checks], summary(checks)
