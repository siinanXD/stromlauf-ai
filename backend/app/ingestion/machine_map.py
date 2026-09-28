"""Maschinenmodell "Schema" aus Daten, ohne Modellaufruf (MB-4).

Zonen = Einbauorte nach IEC 81346 (+ST1, +FE1 ...) aus der Stueckliste, Chips = Betriebsmittel
(Kennzeichen-Index), Verbinder = Leitungen, deren Ortszelle zwei Orte nennt ("+ST1 -> +FE1").
Teile der Draufsicht ohne Einbauort bilden die Zone "Anlage". Reine Funktionen, damit sie ohne
Datenbank testbar sind; die Zeilen kommen aus `tag_occurrences` (Zellen "| a | b | c |").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.fact_card import LOCATION_CELL, _mentions, _rows, location_names, locations_in
from app.ingestion.page_titles import is_parts_list

# Art aus dem Kennbuchstaben (DIN EN 81346-2), fuer Icon und Filter im Modell
KIND_BY_LETTER = {
    "A": "Baugruppe",
    "B": "Sensor",
    "E": "Heizung/Leuchte",
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
# Zweibuchstabige Kennbuchstaben (franzoesisch/international: QF Leistungsschalter, KM Schuetz, EV Elektroventil)
KIND_BY_PAIR = {
    "QF": "Schutz",
    "FU": "Schutz",
    "KM": "Schuetz/Relais",
    "KA": "Schuetz/Relais",
    "KE": "Schuetz/Relais",
    "EV": "Ventil",
    "SB": "Taster",
    "HL": "Meldung",
}
_TAG_LETTER = re.compile(r"^(?:=[\w.]+)?(?:\+[\w-]+)?-?\d{0,2}([A-Z]{1,3})")  # auch Blatt-Stil ohne Minus: 9K1
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
    page: int | None = None  # gesetzt bei Blatt-Zonen aus dem Stromlaufplan (Issue #39)


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
    if not match:
        return ""
    letters = match.group(1)
    return KIND_BY_PAIR.get(letters[:2]) or KIND_BY_LETTER.get(letters[0], "")


def _label(cells: list[str], tag: str) -> str:
    """Bezeichnung aus der Stuecklistenzeile: zuerst die Zelle hinter dem Kennzeichen (Stueckliste: BMK | Bezeichnung),
    sonst die laengste Textzelle, die kein Kennzeichen, Ort oder Bestellnummer ist."""

    def usable(cell: str) -> bool:
        return cell != tag and not LOCATION_CELL.fullmatch(cell) and not locations_in(cell) and not _ORDER_NO.fullmatch(cell)

    # Zellen vor dem Kennzeichen sind Blattnummer, Blatttitel oder Position, nie die Bezeichnung
    after = cells[cells.index(tag) + 1 :] if tag in cells else cells
    for cell in after:
        if usable(cell) and re.search(r"[A-Za-zäöüÄÖÜ]", cell):
            return cell[:60]
    candidates = [c for c in after if usable(c) and re.search(r"[a-zäöü]", c)]
    return max(candidates, key=len)[:60] if candidates else ""


def _row_mentions(cells: list[str], tag: str) -> bool:
    """Tabellenzeile: eigene Zelle. Freie Zeile (Stuecklistenseite einer PDF): Wortgrenze reicht."""
    return tag in cells or (len(cells) == 1 and _mentions(cells, tag))


def _label_after(cell: str, tag: str) -> str:
    """Bezeichnung hinter dem Kennzeichen in einer freien Zeile ("6KE1 Emergency Contactor ..." -> "Emergency ...")."""
    parts = re.split(rf"(?<![\w-]){re.escape(tag)}(?![\w])", cell, maxsplit=1)
    return parts[1].strip(" |:-\t")[:80] if len(parts) == 2 else ""


def build_map(
    bom_rows: list[tuple[str, str]],
    layout_tags: list[tuple[str, str]] | None = None,
    known_tags: set[str] | None = None,
    legend: str = "",
    index_hits: list[tuple[str, int | None, str]] | None = None,
) -> MachineMap:
    """bom_rows: (Kennzeichen, Zeilenkontext) aus der Stueckliste (Datei oder Stuecklistenseite einer PDF);
    layout_tags: (Kennzeichen, Label) aus der Draufsicht; index_hits: (Kennzeichen, Seite, Blatttitel) aus dem
    Kennzeichen-Index der uebrigen Dokumente, erste Fundstelle zuerst; known_tags: alle Betriebsmittel der Quelle.

    Zonen entstehen zuerst aus Einbauorten (+ST1), sonst aus dem Blatt des Stromlaufplans, auf dem das Teil
    zuerst vorkommt (Issue #39); Teile ohne beides landen in "Ohne Einbauort"."""
    names = location_names(legend)
    zones: dict[str, Zone] = {}
    placed: dict[str, str] = {}
    connectors: list[Connector] = []
    labels: dict[str, str] = {}  # Bezeichnung aus einer Stuecklistenzeile ohne Einbauort

    def zone(zone_id: str, code: str | None = None, name: str = "", page: int | None = None) -> Zone:
        if zone_id not in zones:
            zones[zone_id] = Zone(id=zone_id, code=code or zone_id, name=name or names.get(zone_id, ""), page=page)
        return zones[zone_id]

    for tag, context in bom_rows:
        names.update(location_names(context))
        for cells in _rows(context):
            if not _row_mentions(cells, tag):
                continue
            codes = [code for cell in cells for code in locations_in(cell)]
            label = _label(cells, tag) if len(cells) > 1 else _label_after(cells[0], tag)
            if len(codes) >= 2:
                for a, b in zip(codes, codes[1:], strict=False):
                    if not any(c.source == a and c.target == b and c.label == tag for c in connectors):
                        connectors.append(Connector(a, b, tag))
                zone(codes[0])
                zone(codes[1])
                continue
            if tag in placed:
                break
            if codes:
                target = zone(codes[0])
                target.parts.append(Part(tag, label, kind_of(tag), "bom"))
                placed[tag] = target.id
            else:
                labels.setdefault(tag, label)  # Zone kommt aus dem Plan, sonst "Ohne Einbauort"
            break

    for tag, label in layout_tags or []:
        if tag and tag not in placed:
            zone("anlage").parts.append(Part(tag, label, kind_of(tag), "layout"))
            placed[tag] = "anlage"

    only_on_parts_list: list[str] = []
    cable_labels = {c.label for c in connectors}
    for tag, page, section in index_hits or []:
        # Leitungen, Klemmen und Namen ohne Kennbuchstabe (Potentiale wie 24V1) sind keine Teile des Modells
        if not tag or tag in placed or tag in cable_labels or kind_of(tag) in {"", "Leitung", "Klemme"}:
            continue
        if page is None or is_parts_list(section):
            only_on_parts_list.append(tag)
            continue
        target = zone(f"blatt-{page}", f"Blatt {page}", section, page)
        label = labels.pop(tag, None)  # Bezeichnung aus der Stueckliste, wenn es eine Zeile ohne Ort gab
        target.parts.append(Part(tag, label or "", kind_of(tag), "bom" if label is not None else "index"))
        placed[tag] = target.id

    for tag, label in labels.items():
        if tag not in placed:
            zone("?").parts.append(Part(tag, label, kind_of(tag), "bom"))
            placed[tag] = "?"

    for tag in list(dict.fromkeys(only_on_parts_list)) + sorted(known_tags or ()):
        if tag not in placed and kind_of(tag) not in {"", "Leitung", "Klemme"}:
            zone("?").parts.append(Part(tag, "", kind_of(tag), "index"))
            placed[tag] = "?"

    for zone_id, z in zones.items():
        if zone_id == "?":
            z.name = "Ohne Einbauort"
        elif zone_id == "anlage":
            z.name = "Anlage (Draufsicht)"
        z.parts.sort(key=lambda p: (p.kind, p.tag))

    rank = {"anlage": 2, "?": 3}
    ordered = sorted(zones.values(), key=lambda z: (rank.get(z.id, 1 if z.page else 0), z.page or 0, z.id))
    ordered = [z for z in ordered if z.parts or any(c.source == z.id or c.target == z.id for c in connectors)]
    return MachineMap(ordered, connectors)
