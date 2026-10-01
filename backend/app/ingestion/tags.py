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
# Kleinbuchstaben nur direkt hinter einer Ziffer: Etage einer Mehrstockklemme (-X2:3a). Fliesstext hinter
# der Leiste ("-X1:Schirm") wird so kein Anschluss.
_DEVICE_RE = re.compile(
    r"(?<![\w.])"
    r"(?P<prefix>(?:=[A-Z0-9][A-Z0-9.]*)?(?:\+[A-Z0-9][A-Z0-9.\-]*?)?)"
    r"-(?P<letters>[A-Z]{1,3})(?P<number>\d{1,4}(?:\.\d{1,3})?)"
    r"(?::(?P<pin>[A-Z0-9](?:[A-Z0-9+\-]|(?<=\d)[a-z]|[./](?=[A-Z0-9])){0,7}))?"
    r"(?![\w])"
)

# QElectroTech-/franzoesischer Stil ohne Minus: Blattnummer + Kennbuchstabe(n) + Zaehler (4Q1, 9K1, 6KEP1, 5F31).
# Nur wenn ein Dokument diesen Stil durchgaengig nutzt (detect_folio_style), sonst faengt er Bestellnummern wie 6ES7.
_FOLIO_DEVICE_RE = re.compile(r"(?<![\w.:/+=\-])(?P<folio>\d{1,2})(?P<letters>[A-Z]{1,3})(?P<number>\d{1,3})(?![\w.:])")
FOLIO_MIN_HITS = 10

# Schweizer Elektroschema (Issue #91): Klemmleiste ohne Minus, Leerzeichen statt Doppelpunkt ("X420 3" = -X420:3).
# Nur wenn ein Dokument diesen Stil durchgaengig nutzt (detect_spaced_terminals); Dezimalzahlen ("X2 2.5"),
# Profinet-Ports ("X1 P2") und Minus-Kennzeichen ("-X7 2") bleiben draussen.
_SPACED_TERMINAL_RE = re.compile(
    r"(?<![\w.:/+=\-])X(?P<strip>\d{1,4}) (?P<pin>\d{1,3})(?![\w.:/,])"
)
SPACED_MIN_HITS = 5
_DASH_TERMINAL_RE = re.compile(r"(?<![\w.])-X\d{1,4}:[A-Za-z0-9]")

# Bit-Adressen: E 0.0 / I0.0 / %I0.0 / %IX0.0 (deutsche und internationale Mnemonik)
_PLC_BIT_RE = re.compile(r"(?<![\w.])%?(?P<area>[EAIQM])X?[ \t]{0,8}(?P<byte>\d{1,5})\.(?P<bit>[0-7])(?![\w.])")
# Adressbereich einer SPS-Karte: E8.0..E9.7 (Issue #92). Ohne Leerzeichen schliesst _PLC_BIT_RE beide Enden aus,
# weil ein Punkt angrenzt; beide Enden sind Adressen, der Bereich dazwischen wird nicht aufgezaehlt.
_PLC_RANGE_RE = re.compile(
    r"(?<![\w.])%?(?P<area>[EAIQM])X?(?P<byte>\d{1,5})\.(?P<bit>[0-7]) ?\.\. ?"
    r"%?(?P<area2>[EAIQM])X?(?P<byte2>\d{1,5})\.(?P<bit2>[0-7])(?![\w.])"
)
# Byte/Wort/Doppelwort: EB 4, MW 100, %QW20, PEW 256, PAW 256
_PLC_WORD_RE = re.compile(r"(?<![\w.])%?(?P<area>P?[EAIQM])(?P<size>[BWD])[ \t]{0,8}(?P<addr>\d{1,5})(?![\w.])")
# Datenbaustein-Adressen: DB10.DBX 2.0, DB10.DBW4
_PLC_DB_RE = re.compile(
    r"(?<![\w.])DB[ \t]{0,2}(?P<db>\d{1,5})\.DB(?P<size>[XBWD])[ \t]{0,4}(?P<addr>\d{1,5})(?:\.(?P<bit>[0-7]))?(?![\w.])"
)
# EPLAN-Seitenverweis: /12.3 oder =A1+S1/12.3 (Seite.Spalte)
_CROSS_REF_RE = re.compile(r"(?<![a-z/.])/(?P<page>\d{1,4})\.(?P<col>\d{1,2})(?![\w.])")

_INTERNATIONAL_TO_GERMAN = {"I": "E", "Q": "A", "PI": "PE", "PQ": "PA"}

# Anschluesse von Schaltgeraeten nach IEC 60947-1, Anhang L (Issue #98): Spule A1/A2; Kontakte zweistellig aus
# Ordnungs- und Funktionsziffer, Funktionsziffer 1-2 Oeffner, 3-4 Schliesser, 5-6 und 7-8 dasselbe mit
# Sonderfunktion (Ueberlast 95/96 und 97/98, zeitverzoegert); einstellig 1 bis 6 die Hauptkontakte. Das gilt nur fuer
# Schaltgeraete: Schuetze und Relais (K, Q), Taster und Schalter (S), Schutzgeraete (F), Positionsschalter (B).
# Bei einer SPS-Karte (-A1.1:11), einem Sensorstecker (-B1:4) oder einem Motor (-M1:U1) sagt die Nummer nichts.
_PIN_TAG = re.compile(r"-(?P<letters>[A-Z]{1,3})\d{1,4}(?:\.\d{1,3})?:(?P<pin>[A-Z0-9]{1,2})")
_COIL_DEVICES = "KQ"
_CONTACT_DEVICES = "KQSFB"
_MAIN_CONTACT_DEVICES = "KQF"


@dataclass(frozen=True)
class Tag:
    tag: str  # normalisiert
    tag_type: TagType
    context: str


def _german(area: str) -> str:
    return _INTERNATIONAL_TO_GERMAN.get(area, area)


def pin_kind(tag: str) -> str | None:
    """Art eines Geraeteanschlusses: "-K1:A1" Spule, "-K1:13" Schliesser, "-S2:11" Oeffner, "-Q1:2" Hauptkontakt.
    None, wenn die Nummer bei diesem Geraet nichts sagt."""
    match = _PIN_TAG.fullmatch(tag)
    if match is None:
        return None
    first, pin = match["letters"][0], match["pin"]
    if pin in ("A1", "A2"):
        return "Spule" if first in _COIL_DEVICES else None
    if re.fullmatch(r"[1-9][1-8]", pin) and first in _CONTACT_DEVICES:
        return "Öffner" if pin[1] in "1256" else "Schließer"
    if re.fullmatch(r"[1-6]", pin) and first in _MAIN_CONTACT_DEVICES:
        return "Hauptkontakt"
    return None


def normalize_tag(raw: str) -> str:
    """Bringt eine Nutzereingabe ("e 0.0", "K12", "%I0.0") auf die Index-Schreibweise."""
    text = raw.strip().upper()
    tags = extract_tags(text, plc_loose=True)
    if tags:
        return max(tags, key=lambda t: len(t.tag)).tag
    if spaced := _SPACED_TERMINAL_RE.fullmatch(text):  # "X420 3" wie im Schweizer Elektroschema
        return f"-X{spaced['strip']}:{spaced['pin']}"
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


def detect_spaced_terminals(text: str) -> bool:
    """Schreibt das Dokument Klemmen als "X420 3" (Schweizer Elektroschema, Issue #91)?

    Erst ab SPACED_MIN_HITS verschiedenen Klemmen und nur, wenn sie die Klemmen im Minus-Stil ("-X1:5")
    ueberwiegen; ein zufaelliges "X1 2" in einem deutschen Plan schaltet den Stil nicht ein.
    """
    spaced = len({m.group(0) for m in _SPACED_TERMINAL_RE.finditer(text)})
    dash = len({m.group(0) for m in _DASH_TERMINAL_RE.finditer(text)})
    return spaced >= SPACED_MIN_HITS and spaced > dash


def extract_tags(
    text: str,
    *,
    plc_loose: bool = False,
    folio_style: bool = False,
    spaced_terminals: bool = False,
) -> list[Tag]:
    """Findet alle Kennzeichen im Text.

    plc_loose=True akzeptiert auch "A 1.0" mit Leerzeichen in Fliesstext (AWL, Symboltabellen).
    In Plaenen/Handbuechern werden Bit-Adressen mit Leerzeichen nur fuer E/I/Q/M akzeptiert,
    weil "A 1.0" dort meist eine Stromangabe o.ae. ist.
    folio_style=True nimmt zusaetzlich Kennzeichen ohne Minus im Blatt-Stil (4Q1, 9K1), so wie sie dastehen.
    spaced_terminals=True liest "X420 3" als Leiste -X420 und Klemme -X420:3 (detect_spaced_terminals).
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
        if m["pin"]:
            # gross wie normalize_tag(): die Suche vergleicht case-sensitiv, "-x2:3a" sucht "-X2:3A". Anschluesse
            # anderer Geraete (Spule -K1:A1, Kontakt -K1:13) stehen als eigener Typ im Index (Issue #98)
            pin_type = TagType.TERMINAL if is_terminal else TagType.DEVICE_PIN
            add(f"{base}:{m['pin'].upper()}", pin_type, m)

    if folio_style:
        for m in _FOLIO_DEVICE_RE.finditer(text):
            add(m.group(0), TagType.DEVICE, m)

    if spaced_terminals:
        for m in _SPACED_TERMINAL_RE.finditer(text):
            add(f"-X{m['strip']}", TagType.TERMINAL, m)
            add(f"-X{m['strip']}:{m['pin']}", TagType.TERMINAL, m)

    for m in _PLC_BIT_RE.finditer(text):
        has_space = " " in m.group(0) or "\t" in m.group(0)
        if has_space and not plc_loose and m["area"] == "A":
            continue
        add(f"{_german(m['area'])}{int(m['byte'])}.{m['bit']}", TagType.PLC_ADDRESS, m)

    # nach den einzelnen Adressen: "E0.6 .. E1.7" mit Leerzeichen fanden die schon, ihr Kontext bleibt
    for m in _PLC_RANGE_RE.finditer(text):
        add(f"{_german(m['area'])}{int(m['byte'])}.{m['bit']}", TagType.PLC_ADDRESS, m)
        add(f"{_german(m['area2'])}{int(m['byte2'])}.{m['bit2']}", TagType.PLC_ADDRESS, m)

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
