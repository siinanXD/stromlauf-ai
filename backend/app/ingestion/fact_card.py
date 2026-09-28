"""Befundkarte zu einem Betriebsmittel: Einbauort, Bezeichnung, Stromlaufplan-Stellen, Klemmen, SPS-Adressen.

Quelle ist allein der Kennzeichen-Index (Fundstellen mit Textumgebung), nicht das Sprachmodell.
Tabellen (Stueckliste, Klemmenplan, Symboltabelle) liegen dort als "| a | b | | c | d |" vor;
ausgewertet wird nur die Tabellenzeile, in der das Betriebsmittel selbst vorkommt.
"""

import re

from app.ingestion.page_titles import is_parts_list
from app.ingestion.tags import extract_tags
from app.models import TagType

PLC_DOC_TYPES = {"plc_symbols", "plc_program"}
# Einbauort nach IEC 81346: +ST1, +FE1. Leitungen tragen zwei ("+ST1 -> +FE1").
LOCATION_CELL = re.compile(r"\+[A-Za-z][\w-]*")
LOCATION_FILLER = re.compile(r"[\s,;/>.\-–—]+")
# Klartext davor, wie in der Kopfzeile der Stueckliste: "Anlage =FB1, Schaltschrank +ST1, Feld +FE1"
LOCATION_NAME = re.compile(r"([A-ZÄÖÜ][\wäöüß-]+)\s(\+[A-Za-z][\w-]*)")


def locations_in(cell: str) -> list[str]:
    """Ortskennzeichen einer Zelle, aber nur wenn die Zelle aus nichts anderem besteht.

    "+ST1" und "+ST1 -> +FE1" zaehlen, eine Bezeichnung wie "Leitung von +ST1 nach +FE1" nicht.
    """
    codes = LOCATION_CELL.findall(cell)
    rest = LOCATION_FILLER.sub("", LOCATION_CELL.sub("", cell))
    return codes if codes and not rest else []


def location_names(text: str) -> dict[str, str]:
    """Klartext je Ortskennzeichen aus einem Text ("Schaltschrank +ST1" -> {"+ST1": "Schaltschrank"})."""
    return {code: name for name, code in LOCATION_NAME.findall(text or "")}


def _rows(context: str) -> list[list[str]]:
    """Tabellenzeilen ("| a | b | | c |") bzw. Textzeilen (AWL, Symboltabelle) als Zellenlisten."""
    segments = [part for line in context.splitlines() for part in re.split(r"\|\s*\|", line)]
    return [[cell.strip() for cell in segment.split("|") if cell.strip()] for segment in segments]


def _mentions(cells: list[str], tag: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(tag)}(?![\d.])", " ".join(cells)) is not None


def _is_bom(hit: dict) -> bool:
    """Stuecklisten-Datei oder Stuecklistenseite einer PDF (Abschnitt = Seitentitel "Nomenclature", "Stueckliste")."""
    return hit["doc_type"] == "bom" or is_parts_list(hit.get("section"))


def _after(text: str, tag: str) -> str:
    parts = re.split(rf"(?<![\w-]){re.escape(tag)}(?![\w])", text, maxsplit=1)
    return parts[1].strip(" |:-\t")[:80] if len(parts) == 2 else ""


def _value(text: str, hit: dict | None, ref: str, with_page: bool = True) -> dict:
    return {
        "text": text,
        "ref": ref,
        "document_id": hit["document_id"] if hit else None,
        "filename": hit["filename"] if hit else None,
        "page": hit.get("page") if hit and with_page else None,
    }


def _unique(pairs: list[tuple[str, dict]]) -> list[dict]:
    """Erste Fundstelle je Kennzeichen, Reihenfolge wie im Index."""
    seen: dict[str, dict] = {}
    for text, hit in pairs:
        seen.setdefault(text, hit)
    return [_value(text, hit, text) for text, hit in seen.items()]


def hits_of_single_source(hits: list[dict]) -> list[dict] | None:
    """Befundkarte nur eindeutig: stammen die Treffer aus mehreren Quellen (Anlagen), None."""
    sources = {h.get("source_id") for h in hits}
    return hits if len(sources) <= 1 else None


def build_fact_card(tag: str, hits: list[dict], legend: str = "") -> dict | None:
    """Befundkarte oder None, wenn der Index nichts Verwertbares hergibt.

    `legend` ist die Kopfzeile der Stueckliste; daraus wird der Klartext der Einbauorte gelesen.
    """
    title = bom_line = None
    bom_hit = None
    locations: list[str] = []
    # Kopfzeile steht in einer eigenen Zeile, nicht in der des Betriebsmittels: vorab einsammeln
    names = location_names(legend)
    for hit in hits:
        if _is_bom(hit):
            names.update(location_names(hit["context"]))
    sheet_refs: list[str] = []
    terminals: list[tuple[str, dict]] = []
    addresses: list[tuple[str, dict]] = []

    for hit in hits:
        is_bom = _is_bom(hit)
        for cells in _rows(hit["context"]):
            if not _mentions(cells, tag):
                continue
            found = extract_tags(" ".join(cells), plc_loose=hit["doc_type"] in PLC_DOC_TYPES)
            if is_bom:
                locations += [code for cell in cells for code in locations_in(cell)]
                bom_hit = bom_hit or hit
            if is_bom and title is None:
                bom_line = " | ".join(cells)
                if tag in cells and cells.index(tag) + 1 < len(cells):
                    title = cells[cells.index(tag) + 1]
                elif len(cells) == 1:  # freie Zeile einer Stuecklistenseite: Text hinter dem Kennzeichen
                    title = _after(cells[0], tag) or None
            if is_bom or hit["doc_type"] == "terminal_plan":
                sheet_refs += [t.tag for t in found if t.tag_type == TagType.CROSS_REF]
            if hit["doc_type"] == "terminal_plan":
                terminals += [(t.tag, hit) for t in found if t.tag_type == TagType.TERMINAL and t.tag.startswith("-X") and ":" in t.tag]
            if hit["doc_type"] in PLC_DOC_TYPES:
                addresses += [(t.tag, hit) for t in found if t.tag_type == TagType.PLC_ADDRESS]

    schematic_hits = [h for h in hits if h["doc_type"] == "schematic" and not _is_bom(h)]
    schematic = schematic_hits[0] if schematic_hits else None
    sheets = {int(ref.lstrip("/").split(".")[0]) for ref in sheet_refs if re.fullmatch(r"/\d+\.\d+", ref)}
    schematic_values = [_value(ref, schematic, ref, with_page=False) for ref in dict.fromkeys(sheet_refs)]
    for hit in schematic_hits if not sheets else []:  # genaue Verweise schlagen blosse Seiten
        page = hit.get("page")
        if page and f"S. {page}" not in [v["text"] for v in schematic_values]:
            schematic_values.append(_value(f"S. {page}", hit, f"S. {page}"))

    location_values = [
        _value(f"{names[code]} {code}" if code in names else code, bom_hit, code)
        for code in dict.fromkeys(locations)
    ]
    rows = [
        {"label": "Einbauort", "values": location_values},
        {"label": "Stromlaufplan", "values": schematic_values},
        {"label": "Klemmen", "values": _unique(terminals)},
        {"label": "SPS", "values": _unique(addresses)},
    ]
    rows = [row for row in rows if row["values"]]
    if not rows and title is None:
        return None
    return {"tag": tag, "title": title, "bom_line": bom_line, "rows": rows}
