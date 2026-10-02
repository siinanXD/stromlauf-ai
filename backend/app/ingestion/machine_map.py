"""Maschinenmodell "Schema" aus Daten, ohne Modellaufruf (MB-4).

Zonen = Einbauorte nach IEC 81346 (+ST1, +FE1 ...) aus der Stueckliste, Chips = Betriebsmittel
(Kennzeichen-Index), Verbinder = Leitungen, deren Ortszelle zwei Orte nennt ("+ST1 -> +FE1").
Reine Funktionen, damit sie ohne Datenbank testbar sind; die Zeilen kommen aus `tag_occurrences`
(Zellen "| a | b | c |").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.fact_card import LOCATION_CELL, _mentions, _rows, location_names, locations_in
from app.ingestion.letter_codes import OFFEN, Edition, detect_edition, is_part, kind_of, verb_of
from app.ingestion.page_titles import is_parts_list

_ORDER_NO = re.compile(r"^[\dA-Z][\w./-]{4,}$")


@dataclass
class Part:
    tag: str
    label: str = ""
    kind: str = ""
    source: str = "bom"  # bom | index
    verb: str = ""  # Beziehung im Bauteil-Sheet ("schaltet"), aus der Art (Issue #99)


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
    edition: Edition = field(default_factory=lambda: Edition(OFFEN, ""))

    def as_dict(self) -> dict:
        return {
            "zones": [
                {"id": z.id, "code": z.code, "name": z.name, "parts": [p.__dict__ for p in z.parts]} for z in self.zones
            ],
            "connectors": [c.__dict__ for c in self.connectors],
            "part_count": sum(len(z.parts) for z in self.zones),
            "letter_codes": {"edition": self.edition.name, "reason": self.edition.reason},
        }


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
    known_tags: set[str] | None = None,
    legend: str = "",
    index_hits: list[tuple[str, int | None, str, int | None]] | None = None,
) -> MachineMap:
    """bom_rows: (Kennzeichen, Zeilenkontext) aus der Stueckliste (Datei oder Stuecklistenseite einer PDF);
    index_hits: (Kennzeichen, Seite, Blatttitel, Blatt aus dem Schriftfeld oder None) aus dem Kennzeichen-Index der
    uebrigen Dokumente, erste Fundstelle zuerst; known_tags: alle Betriebsmittel der Quelle.

    Zonen entstehen zuerst aus Einbauorten (+ST1), sonst aus dem Blatt des Stromlaufplans, auf dem das Teil
    zuerst vorkommt (Issue #39); Teile ohne beides landen in "Ohne Einbauort". Die Blatt-Zone traegt die Nummer aus
    dem Schriftfeld; ohne gelesene Nummer heisst sie nach der Seite (Issue #67)."""
    names = location_names(legend)
    # Lesart der Kennbuchstaben aus allen Kennzeichen der Quelle (Issue #99)
    edition = detect_edition(
        [tag for tag, _ in bom_rows] + [hit[0] for hit in index_hits or []] + sorted(known_tags or ())
    )
    zones: dict[str, Zone] = {}
    placed: dict[str, str] = {}
    connectors: list[Connector] = []
    labels: dict[str, str] = {}  # Bezeichnung aus einer Stuecklistenzeile ohne Einbauort

    def part(tag: str, label: str, source: str) -> Part:
        kind = kind_of(tag, edition.name)
        return Part(tag, label, kind, source, verb_of(kind))

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
                target.parts.append(part(tag, label, "bom"))
                placed[tag] = target.id
            else:
                labels.setdefault(tag, label)  # Zone kommt aus dem Plan, sonst "Ohne Einbauort"
            break

    only_on_parts_list: list[str] = []
    cable_labels = {c.label for c in connectors}
    for tag, page, section, sheet in index_hits or []:
        # Leitungen, Klemmen und Namen ohne Kennbuchstabe (Potentiale wie 24V1) sind keine Teile des Modells
        if not tag or tag in placed or tag in cable_labels or not is_part(tag, edition.name):
            continue
        if page is None or is_parts_list(section):
            only_on_parts_list.append(tag)
            continue
        if sheet is not None:
            target = zone(f"blatt-{sheet}", f"Blatt {sheet}", section, page)
        else:  # keine Blattnummer im Schriftfeld gelesen: nicht raten, die Seite nennen
            target = zone(f"seite-{page}", f"Seite {page}", section, page)
        label = labels.pop(tag, None)  # Bezeichnung aus der Stueckliste, wenn es eine Zeile ohne Ort gab
        target.parts.append(part(tag, label or "", "bom" if label is not None else "index"))
        placed[tag] = target.id

    for tag, label in labels.items():
        if tag not in placed:
            zone("?").parts.append(part(tag, label, "bom"))
            placed[tag] = "?"

    for tag in list(dict.fromkeys(only_on_parts_list)) + sorted(known_tags or ()):
        if tag not in placed and is_part(tag, edition.name):
            zone("?").parts.append(part(tag, "", "index"))
            placed[tag] = "?"

    for zone_id, z in zones.items():
        if zone_id == "?":
            z.name = "Ohne Einbauort"
        z.parts.sort(key=lambda p: (p.kind, p.tag))

    rank = {"?": 3}
    ordered = sorted(zones.values(), key=lambda z: (rank.get(z.id, 1 if z.page else 0), z.page or 0, z.id))
    ordered = [z for z in ordered if z.parts or any(c.source == z.id or c.target == z.id for c in connectors)]
    return MachineMap(ordered, connectors, edition)
