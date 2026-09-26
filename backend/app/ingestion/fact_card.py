"""Befundkarte zu einem Betriebsmittel: Bezeichnung, Stromlaufplan-Stellen, Klemmen, SPS-Adressen.

Quelle ist allein der Kennzeichen-Index (Fundstellen mit Textumgebung), nicht das Sprachmodell.
Tabellen (Stueckliste, Klemmenplan, Symboltabelle) liegen dort als "| a | b | | c | d |" vor;
ausgewertet wird nur die Tabellenzeile, in der das Betriebsmittel selbst vorkommt.
"""

import re

from app.ingestion.tags import extract_tags
from app.models import TagType

PLC_DOC_TYPES = {"plc_symbols", "plc_program"}


def _rows(context: str) -> list[list[str]]:
    """Tabellenzeilen ("| a | b | | c |") bzw. Textzeilen (AWL, Symboltabelle) als Zellenlisten."""
    segments = [part for line in context.splitlines() for part in re.split(r"\|\s*\|", line)]
    return [[cell.strip() for cell in segment.split("|") if cell.strip()] for segment in segments]


def _mentions(cells: list[str], tag: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(tag)}(?![\d.])", " ".join(cells)) is not None


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


def build_fact_card(tag: str, hits: list[dict]) -> dict | None:
    """Befundkarte oder None, wenn der Index nichts Verwertbares hergibt."""
    title = bom_line = None
    sheet_refs: list[str] = []
    terminals: list[tuple[str, dict]] = []
    addresses: list[tuple[str, dict]] = []

    for hit in hits:
        for cells in _rows(hit["context"]):
            if not _mentions(cells, tag):
                continue
            found = extract_tags(" ".join(cells), plc_loose=hit["doc_type"] in PLC_DOC_TYPES)
            if hit["doc_type"] == "bom" and title is None:
                bom_line = " | ".join(cells)
                if tag in cells and cells.index(tag) + 1 < len(cells):
                    title = cells[cells.index(tag) + 1]
            if hit["doc_type"] in {"bom", "terminal_plan"}:
                sheet_refs += [t.tag for t in found if t.tag_type == TagType.CROSS_REF]
            if hit["doc_type"] == "terminal_plan":
                terminals += [(t.tag, hit) for t in found if t.tag_type == TagType.TERMINAL and t.tag.startswith("-X") and ":" in t.tag]
            if hit["doc_type"] in PLC_DOC_TYPES:
                addresses += [(t.tag, hit) for t in found if t.tag_type == TagType.PLC_ADDRESS]

    schematic_hits = [h for h in hits if h["doc_type"] == "schematic"]
    schematic = schematic_hits[0] if schematic_hits else None
    sheets = {int(ref.lstrip("/").split(".")[0]) for ref in sheet_refs if re.fullmatch(r"/\d+\.\d+", ref)}
    schematic_values = [_value(ref, schematic, ref, with_page=False) for ref in dict.fromkeys(sheet_refs)]
    for hit in schematic_hits if not sheets else []:  # genaue Verweise schlagen blosse Seiten
        page = hit.get("page")
        if page and f"S. {page}" not in [v["text"] for v in schematic_values]:
            schematic_values.append(_value(f"S. {page}", hit, f"S. {page}"))

    rows = [
        {"label": "Stromlaufplan", "values": schematic_values},
        {"label": "Klemmen", "values": _unique(terminals)},
        {"label": "SPS", "values": _unique(addresses)},
    ]
    rows = [row for row in rows if row["values"]]
    if not rows and title is None:
        return None
    return {"tag": tag, "title": title, "bom_line": bom_line, "rows": rows}
