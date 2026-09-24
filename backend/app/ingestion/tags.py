"""Erkennung von Kennzeichen in Text: BMK, Klemmen, SPS-Adressen, Seitenverweise.

Die normalisierten Tags verbinden Stromlaufplan, Stueckliste, Klemmenplan und AWL-Programm:
"-K12" im Plan, "-K12" in der Stueckliste, "E 0.0" im AWL und "E0.0" an der SPS-Karte
landen unter demselben Schluessel im Index.
"""

import re
from dataclasses import dataclass

from app.models import TagType

# IEC 81346 / EN 61346: [=Anlage][+Ort]-Kennbuchstabe(n)Zaehlnummer[:Anschluss]
_DEVICE_RE = re.compile(
    r"(?<![\w.])"
    r"(?P<prefix>(?:=[A-Z0-9][A-Z0-9.]*)?(?:\+[A-Z0-9][A-Z0-9.\-]*?)?)"
    r"-(?P<letters>[A-Z]{1,3})(?P<number>\d{1,4}(?:\.\d{1,3})?)"
    r"(?::(?P<pin>[A-Z0-9][A-Z0-9./+\-]{0,7}))?"
    r"(?![\w])"
)

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


def _snippet(text: str, start: int, end: int, width: int = 80) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    return " ".join(text[left:right].split())


def extract_tags(text: str, *, plc_loose: bool = False) -> list[Tag]:
    """Findet alle Kennzeichen im Text.

    plc_loose=True akzeptiert auch "A 1.0" mit Leerzeichen in Fliesstext (AWL, Symboltabellen).
    In Plaenen/Handbuechern werden Bit-Adressen mit Leerzeichen nur fuer E/I/Q/M akzeptiert,
    weil "A 1.0" dort meist eine Stromangabe o.ae. ist.
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
