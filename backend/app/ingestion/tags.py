"""Erkennung von Kennzeichen in Text: BMK, Klemmen, SPS-Adressen, Seitenverweise.

Die normalisierten Tags verbinden Stromlaufplan, Stueckliste, Klemmenplan und AWL-Programm:
"-K12" im Plan, "-K12" in der Stueckliste, "E 0.0" im AWL und "E0.0" an der SPS-Karte
landen unter demselben Schluessel im Index.
"""

import re
from dataclasses import dataclass

from app.models import TagType

# IEC 81346 / EN 61346: [=Anlage][+Ort]-Kennbuchstabe(n)Zaehlnummer[:Anschluss]
# Im Anschluss stehen "." und "/" nur vor einem Buchstaben oder einer Ziffer (-X5:1.2, -X4:U/V/W): so bleiben
# Satzende ("-X3:6.") und das naechste Kennzeichen ("-X3:9/-X3:10") draussen.
_DEVICE_RE = re.compile(
    r"(?<![\w.])"
    r"(?P<prefix>(?:=[A-Z0-9][A-Z0-9.]*)?(?:\+[A-Z0-9][A-Z0-9.\-]*?)?)"
    r"-(?P<letters>[A-Z]{1,3})(?P<number>\d{1,4}(?:\.\d{1,3})?)"
    r"(?::(?P<pin>[A-Z0-9](?:[A-Z0-9+\-]|[./](?=[A-Z0-9])){0,7}))?"
    r"(?![\w])"
)

# QElectroTech-/franzoesischer Stil ohne Minus: Blattnummer + Kennbuchstabe(n) + Zaehler (4Q1, 9K1, 6KEP1, 5F31).
# Nur wenn ein Dokument diesen Stil durchgaengig nutzt (detect_folio_style), sonst faengt er Bestellnummern wie 6ES7.
_FOLIO_DEVICE_RE = re.compile(r"(?<![\w.:/+=\-])(?P<folio>\d{1,2})(?P<letters>[A-Z]{1,3})(?P<number>\d{1,3})(?![\w.:])")
FOLIO_MIN_HITS = 10

# Bit-Adressen: E 0.0 / I0.0 / %I0.0 / %IX0.0 (deutsche und internationale Mnemonik)
_PLC_BIT_RE = re.compile(r"(?<![\w.])%?(?P<area>[EAIQM])X?[ \t]{0,8}(?P<byte>\d{1,5})\.(?P<bit>[0-7])(?![\w.])")
# Byte/Wort/Doppelwort: EB 4, MW 100, %QW20, PEW 256, PAW 256
_PLC_WORD_RE = re.compile(r"(?<![\w.])%?(?P<area>P?[EAIQM])(?P<size>[BWD])[ \t]{0,8}(?P<addr>\d{1,5})(?![\w.])")
# Datenbaustein-Adressen: DB10.DBX 2.0, DB10.DBW4
_PLC_DB_RE = re.compile(
    r"(?<![\w.])DB[ \t]{0,2}(?P<db>\d{1,5})\.DB(?P<size>[XBWD])[ \t]{0,4}(?P<addr>\d{1,5})(?:\.(?P<bit>[0-7]))?(?![\w.])"
)
# EPLAN-Seitenverweis: /12.3 oder =A1+S1/12.3 (Seite.Spalte)
_CROSS_REF_RE = re.compile(r"(?<![a-z/.])/(?P<page>\d{1,4})\.(?P<col>\d{1,2})(?![\w.])")

_INTERNATIONAL_TO_GERMAN = {"I": "E", "Q": "A", "PI": "PE", "PQ": "PA"}


@dataclass(frozen=True)
class Tag:
    tag: str  # normalisiert
    tag_type: TagType
    context: str


def _german(area: str) -> str:
    return _INTERNATIONAL_TO_GERMAN.get(area, area)


def normalize_tag(raw: str) -> str:
    """Bringt eine Nutzereingabe ("e 0.0", "K12", "%I0.0") auf die Index-Schreibweise."""
    text = raw.strip().upper()
    tags = extract_tags(text, plc_loose=True)
    if tags:
        return max(tags, key=lambda t: len(t.tag)).tag
    compact = re.sub(r"\s+", "", text)
    if re.fullmatch(r"[A-Z]{1,3}\d{1,4}(?:\.\d{1,3})?(?::[A-Z0-9./+\-]{1,8})?", compact):
        return "-" + compact
    return compact


def search_key(query: str) -> str | None:
    """Suchpraefix fuer die globale Suche; None bei leerer oder sinnloser Eingabe."""
    if not query or not query.strip():
        return None
    key = normalize_tag(query)
    return key if re.search(r"[A-Z0-9]", key) else None


def search_prefixes(query: str) -> list[str]:
    """Praefixe fuer die Suche beim Tippen: normalisiert, roh und mit Minus ("e0" -> E0, -E0)."""
    key = search_key(query)
    if key is None:
        return []
    compact = re.sub(r"\s+", "", query.upper())
    candidates = [key, compact]
    if compact[:1] not in "-=+%":
        candidates.append("-" + compact)
    return list(dict.fromkeys(c for c in candidates if re.search(r"[A-Z0-9]", c)))


_TABLE_ROW_MAX = 600  # Zeichen; laengere "Zeilen" sind keine Tabellenzeilen mehr, sondern Fliesstext mit Strichen


def _snippet(text: str, start: int, end: int, width: int = 80) -> str:
    """Kontext einer Fundstelle: in einer Markdown-Tabelle die ganze eigene Zeile, sonst ein Fenster von `width` Zeichen.

    Die ganze Zeile brauchen Befundkarte und Maschinenmodell fuer den Einbauort (Issue #38): das Fenster schnitt die
    Zelle am Zeilenende ab und zeigte stattdessen das Ende der Vorgaengerzeile mit deren Einbauort.
    """
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end].strip()
    if line.startswith("|") and line.endswith("|") and len(line) <= _TABLE_ROW_MAX:
        return _table_row(line)
    left = max(0, start - width)
    right = min(len(text), end + width)
    return " ".join(text[left:right].split())


def _table_row(line: str) -> str:
    """Tabellenzeile bereinigt: leere Zellen raus, verbundene Zellen (Docling wiederholt sie: "| 6 | 6 |") nur einmal."""
    cells: list[str] = []
    for cell in line.strip("|").split("|"):
        cell = " ".join(cell.split())
        if cell and (not cells or cells[-1] != cell):
            cells.append(cell)
    return "| " + " | ".join(cells) + " |" if cells else "|"


def detect_folio_style(text: str) -> bool:
    """Schreibt das Dokument Kennzeichen ohne Minus (QET-Stil: 4Q1, 9K1)?

    Erst ab FOLIO_MIN_HITS verschiedenen Treffern und nur, wenn sie die Minus-Kennzeichen deutlich ueberwiegen;
    deutsche Plaene mit Bestellnummern (6ES7 214) bleiben so beim Minus-Stil.
    """
    folio = len({m.group(0) for m in _FOLIO_DEVICE_RE.finditer(text)})
    dash = len({m.group(0) for m in _DEVICE_RE.finditer(text)})
    return folio >= FOLIO_MIN_HITS and folio > 2 * dash


def extract_tags(text: str, *, plc_loose: bool = False, folio_style: bool = False) -> list[Tag]:
    """Findet alle Kennzeichen im Text.

    plc_loose=True akzeptiert auch "A 1.0" mit Leerzeichen in Fliesstext (AWL, Symboltabellen).
    In Plaenen/Handbuechern werden Bit-Adressen mit Leerzeichen nur fuer E/I/Q/M akzeptiert,
    weil "A 1.0" dort meist eine Stromangabe o.ae. ist.
    folio_style=True nimmt zusaetzlich Kennzeichen ohne Minus im Blatt-Stil (4Q1, 9K1), so wie sie dastehen.
    """
    found: dict[tuple[str, str], Tag] = {}

    def add(tag: str, tag_type: TagType, match: re.Match) -> None:
        key = (tag, tag_type)
        if key not in found:
            found[key] = Tag(tag, tag_type, _snippet(text, match.start(), match.end()))

    for m in _DEVICE_RE.finditer(text):
        base = f"-{m['letters']}{m['number']}"
        is_terminal = m["letters"].startswith("X")
        tag_type = TagType.TERMINAL if is_terminal else TagType.DEVICE
        add(base, tag_type, m)
        if m["prefix"]:
            add(f"{m['prefix']}{base}", tag_type, m)
        if m["pin"] and is_terminal:
            add(f"{base}:{m['pin']}", TagType.TERMINAL, m)

    if folio_style:
        for m in _FOLIO_DEVICE_RE.finditer(text):
            add(m.group(0), TagType.DEVICE, m)

    for m in _PLC_BIT_RE.finditer(text):
        has_space = " " in m.group(0) or "\t" in m.group(0)
        if has_space and not plc_loose and m["area"] == "A":
            continue
        add(f"{_german(m['area'])}{int(m['byte'])}.{m['bit']}", TagType.PLC_ADDRESS, m)

    for m in _PLC_WORD_RE.finditer(text):
        add(f"{_german(m['area'])}{m['size']}{int(m['addr'])}", TagType.PLC_ADDRESS, m)

    for m in _PLC_DB_RE.finditer(text):
        tag = f"DB{int(m['db'])}.DB{m['size']}{int(m['addr'])}"
        if m["bit"] is not None:
            tag += f".{m['bit']}"
        add(tag, TagType.PLC_ADDRESS, m)
        add(f"DB{int(m['db'])}", TagType.PLC_ADDRESS, m)

    for m in _CROSS_REF_RE.finditer(text):
        add(f"/{int(m['page'])}.{int(m['col'])}", TagType.CROSS_REF, m)

    return list(found.values())
