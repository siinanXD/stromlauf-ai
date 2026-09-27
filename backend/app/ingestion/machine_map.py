"""Maschinenmodell "Schema" aus Daten, ohne Modellaufruf (MB-4).

Zonen = Einbauorte nach IEC 81346 (+ST1, +FE1 ...) aus der Stueckliste, Chips = Betriebsmittel
(Kennzeichen-Index), Verbinder = Leitungen, deren Ortszelle zwei Orte nennt ("+ST1 -> +FE1").
Teile der Draufsicht ohne Einbauort bilden die Zone "Anlage". Reine Funktionen, damit sie ohne
Datenbank testbar sind; die Zeilen kommen aus `tag_occurrences` (Zellen "| a | b | c |").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.fact_card import LOCATION_CELL, _rows, location_names, locations_in

# Art aus dem Kennbuchstaben (DIN EN 81346-2), fuer Icon und Filter im Modell
KIND_BY_LETTER = {
    "A": "Baugruppe",
    "B": "Sensor",
    "F": "Schutz",
    "G": "Versorgung",
    "H": "Meldung",
    "K": "Schuetz/Relais",
    "M": "Motor",
    "P": "Anzeige",
    "Q": "Schalter",
    "R": "Widerstand",
    "S": "Taster",
    "T": "Trafo",
    "U": "Umrichter",
    "W": "Leitung",
    "X": "Klemme",
    "Y": "Ventil",
}
_TAG_LETTER = re.compile(r"^(?:\+[\w-]+)?-?([A-Z])")
_ORDER_NO = re.compile(r"^[\dA-Z][\w./-]{4,}$")


@dataclass
class Part:
    tag: str
    label: str = ""
    kind: str = ""
    source: str = "bom"  # bom | layout | index


@dataclass
class Zone:
    id: str
    code: str
    name: str
    parts: list[Part] = field(default_factory=list)


@dataclass
class Connector:
    source: str
    target: str
    label: str = ""


@dataclass
class MachineMap:
    zones: list[Zone]
    connectors: list[Connector]

    def as_dict(self) -> dict:
        return {
            "zones": [
                {"id": z.id, "code": z.code, "name": z.name, "parts": [p.__dict__ for p in z.parts]} for z in self.zones
            ],
            "connectors": [c.__dict__ for c in self.connectors],
            "part_count": sum(len(z.parts) for z in self.zones),
        }


def kind_of(tag: str) -> str:
    match = _TAG_LETTER.match(tag.upper())
    return KIND_BY_LETTER.get(match.group(1), "") if match else ""


def _label(cells: list[str], tag: str) -> str:
    """Bezeichnung aus der Stuecklistenzeile: die laengste Textzelle, die kein Kennzeichen, Ort oder Bestellnummer ist."""
    candidates = [
        c
        for c in cells
        if c != tag and not LOCATION_CELL.fullmatch(c) and not locations_in(c) and not _ORDER_NO.fullmatch(c) and re.search(r"[a-zäöü]", c)
    ]
    return max(candidates, key=len)[:60] if candidates else ""


def build_map(
    bom_rows: list[tuple[str, str]],
    layout_tags: list[tuple[str, str]] | None = None,
    known_tags: set[str] | None = None,
    legend: str = "",
) -> MachineMap:
    """bom_rows: (Kennzeichen, Zeilenkontext) aus dem Index der Stueckliste; layout_tags: (Kennzeichen, Label)
    aus der Draufsicht; known_tags: alle Betriebsmittel der Quelle (landen ohne Ort in "Ohne Einbauort")."""
    names = location_names(legend)
    zones: dict[str, Zone] = {}
    placed: dict[str, str] = {}
    connectors: list[Connector] = []

    def zone(code: str) -> Zone:
        if code not in zones:
            zones[code] = Zone(id=code, code=code, name=names.get(code, ""))
        return zones[code]

    for tag, context in bom_rows:
        names.update(location_names(context))
        for cells in _rows(context):
            if tag not in cells:
                continue
            codes = [code for cell in cells for code in locations_in(cell)]
            label = _label(cells, tag)
            if len(codes) >= 2:
                for a, b in zip(codes, codes[1:], strict=False):
                    if not any(c.source == a and c.target == b and c.label == tag for c in connectors):
                        connectors.append(Connector(a, b, tag))
                zone(codes[0])
                zone(codes[1])
                continue
            if tag in placed:
                continue
            target = zone(codes[0]) if codes else zone("?")
            target.parts.append(Part(tag, label, kind_of(tag), "bom"))
            placed[tag] = target.id
            break

    for tag, label in layout_tags or []:
        if tag and tag not in placed:
            zone("anlage").parts.append(Part(tag, label, kind_of(tag), "layout"))
            placed[tag] = "anlage"

    for tag in sorted(known_tags or ()):
        if tag not in placed and kind_of(tag) not in {"", "Leitung", "Klemme"}:
            zone("?").parts.append(Part(tag, "", kind_of(tag), "index"))
            placed[tag] = "?"

    for code, z in zones.items():
        if code == "?":
            z.name = "Ohne Einbauort"
        elif code == "anlage":
            z.name = "Anlage (Draufsicht)"
        z.parts.sort(key=lambda p: (p.kind, p.tag))

    ordered = sorted(zones.values(), key=lambda z: (z.id in {"anlage", "?"}, z.id == "?", z.id))
    ordered = [z for z in ordered if z.parts or any(c.source == z.id or c.target == z.id for c in connectors)]
    return MachineMap(ordered, connectors)
