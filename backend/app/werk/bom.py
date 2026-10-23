"""Stueckliste aus der Schrankerkennung (SIN-732): gleiche Bauteile gruppieren, zaehlen, BMK vergeben.

Reine Logik ohne Datenbank und Modell. Eingang sind die Rahmen eines Schrankbilds (Art, Beschriftung, Lage,
Sicherheit) und je Rahmen optional das gelesene Typenschild (Hersteller, Typ, Artikelnummer). Gruppiert wird nach
Art plus Artikelnummer; ohne Artikelnummer nach Art plus Typ bzw. Beschriftung. Die BMK-Vorschlaege folgen den
Kennbuchstaben nach IEC 81346-2 (K Schuetz/Relais, F Sicherung, Q Schalter, ...) und werden in Leserichtung
(oben links nach unten rechts) durchnummeriert. Bereits vergebene Kennzeichen bleiben, solange sie eindeutig sind.
"""

import re
from dataclasses import dataclass, field

UNSURE_BELOW = 0.7  # Sicherheit darunter: Zeile ist zu pruefen
ROW_BAND = 0.04  # Rahmen, deren Mitte hoechstens so weit (relativ zur Bildhoehe) auseinanderliegt, sind eine Zeile

# Schluesselwort der Art -> Kennbuchstabe; der erste Treffer gewinnt, daher spezifisch vor allgemein.
LETTER_BY_KEYWORD: tuple[tuple[str, str], ...] = (
    ("motorschutz", "Q"),
    ("leistungsschalter", "Q"),
    ("hauptschalter", "Q"),
    ("trennschalter", "Q"),
    ("fi", "F"),
    ("sicherung", "F"),
    ("ls-schalter", "F"),
    ("leitungsschutz", "F"),
    ("überspannung", "F"),
    ("ueberspannung", "F"),
    ("schütz", "K"),
    ("schuetz", "K"),
    ("relais", "K"),
    ("koppelrelais", "K"),
    ("klemme", "X"),
    ("stecker", "X"),
    ("netzteil", "G"),
    ("spannungsversorgung", "G"),
    ("sps", "A"),
    ("steuerung", "A"),
    ("sicherheitsrelais", "K"),
    ("umrichter", "T"),
    ("transformator", "T"),
    ("trafo", "T"),
    ("taster", "S"),
    ("leuchtmelder", "H"),
    ("leuchte", "H"),
    ("lüfter", "E"),
    ("luefter", "E"),
    ("heizung", "E"),
    ("kabelkanal", "W"),
    ("leitung", "W"),
    ("schalter", "Q"),
)
DEFAULT_LETTER = "A"  # nicht zuordenbar: Baugruppe

_TAG_RE = re.compile(r"^-([A-Z]+)(\d+)$")
_SEPARATORS = re.compile(r"[\s\-./_]+")


@dataclass(frozen=True)
class BomItem:
    """Ein Rahmen im Schrankbild samt gelesenem Typenschild."""

    id: str
    kind: str = ""
    label: str = ""
    tag: str = ""
    x: float = 0.0
    y: float = 0.0
    w: float = 0.1
    h: float = 0.1
    confidence: float | None = None
    manufacturer: str = ""
    type: str = ""
    order_number: str = ""
    rating: str = ""  # Nennwerte, z. B. "24 V DC, 10 A"


@dataclass
class BomRow:
    number: int  # laufende Nummer, steht auch im Kasten auf dem Foto
    bmk: list[str]
    quantity: int
    part: str
    manufacturer: str
    type: str
    order_number: str
    rating: str
    confidence: float | None
    review: bool
    item_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "number": self.number,
            "bmk": self.bmk,
            "quantity": self.quantity,
            "part": self.part,
            "manufacturer": self.manufacturer,
            "type": self.type,
            "order_number": self.order_number,
            "rating": self.rating,
            "confidence": self.confidence,
            "review": self.review,
            "item_ids": self.item_ids,
        }


@dataclass
class Bom:
    rows: list[BomRow]
    bmk_by_item: dict[str, str]  # Rahmen -> vergebenes BMK
    number_by_item: dict[str, int]  # Rahmen -> laufende Nummer seiner Zeile

    @property
    def total(self) -> int:
        return sum(row.quantity for row in self.rows)


def _squash(text: str) -> str:
    return _SEPARATORS.sub("", text).upper()


def letter_for(kind: str, label: str = "") -> str:
    """Kennbuchstabe aus Art und Beschriftung; ganze Woerter vor Teilstuecken, damit „FI“ nicht in „Frequenz…“ trifft."""
    text = f"{kind} {label}".lower()
    words = set(re.findall(r"[a-zäöüß0-9\-]+", text))
    for keyword, letter in LETTER_BY_KEYWORD:
        if len(keyword) <= 2:
            if keyword in words:
                return letter
        elif keyword in text:
            return letter
    return DEFAULT_LETTER


def reading_order(items: list[BomItem]) -> list[BomItem]:
    """Oben links nach unten rechts: Zeilen nach Mitte-y in Baendern, innerhalb der Zeile nach x."""
    ordered = sorted(items, key=lambda i: (i.y + i.h / 2, i.x))
    rows: list[list[BomItem]] = []
    anchor = None
    for item in ordered:
        centre = item.y + item.h / 2
        if anchor is None or centre - anchor > ROW_BAND:
            rows.append([])
            anchor = centre
        rows[-1].append(item)
    return [item for row in rows for item in sorted(row, key=lambda i: (i.x, i.y))]


def assign_bmk(items: list[BomItem]) -> dict[str, str]:
    """Rahmen-ID -> eindeutiges BMK. Ein vorhandenes Kennzeichen bleibt, wenn es die Form `-K12` hat und nur
    einmal vorkommt (das erste in Leserichtung behaelt es); alle anderen bekommen die naechste freie Nummer
    ihres Kennbuchstabens, in Leserichtung."""
    ordered = reading_order(items)
    taken: set[str] = set()
    result: dict[str, str] = {}
    for item in ordered:
        tag = _normalize(item.tag)
        if _TAG_RE.match(tag) and tag not in taken:
            taken.add(tag)
            result[item.id] = tag
    counters: dict[str, int] = {}
    for item in ordered:
        if item.id in result:
            continue
        letter = letter_for(item.kind, item.label)
        number = counters.get(letter, 0)
        while True:
            number += 1
            candidate = f"-{letter}{number}"
            if candidate not in taken:
                break
        counters[letter] = number
        taken.add(candidate)
        result[item.id] = candidate
    return result


def _group_key(item: BomItem) -> tuple[str, str]:
    kind = item.kind.strip().lower() or item.label.strip().lower()
    order = _squash(item.order_number)
    if order:
        return kind, order
    return kind, _squash(item.type) or _squash(item.label)


def _bmk_sort_key(bmk: str) -> tuple[str, int]:
    match = _TAG_RE.match(bmk)
    return (match.group(1), int(match.group(2))) if match else (bmk, 0)


def build_bom(items: list[BomItem]) -> Bom:
    """Zeilen in der Reihenfolge des ersten Auftretens in Leserichtung; die Menge ist die Zahl der Rahmen."""
    bmk = assign_bmk(items)
    groups: dict[tuple[str, str], list[BomItem]] = {}
    for item in reading_order(items):
        groups.setdefault(_group_key(item), []).append(item)
    rows: list[BomRow] = []
    number_by_item: dict[str, int] = {}
    for number, members in enumerate(groups.values(), start=1):
        first = members[0]
        confidences = [m.confidence for m in members if m.confidence is not None]
        lowest = min(confidences) if confidences else None
        rows.append(
            BomRow(
                number=number,
                bmk=sorted((bmk[m.id] for m in members), key=_bmk_sort_key),
                quantity=len(members),
                part=first.kind.strip() or first.label.strip(),
                manufacturer=_first(m.manufacturer for m in members),
                type=_first(m.type for m in members) or first.label.strip(),
                order_number=_first(m.order_number for m in members),
                rating=_first(m.rating for m in members),
                confidence=lowest,
                review=lowest is not None and lowest < UNSURE_BELOW,
                item_ids=[m.id for m in members],
            )
        )
        for member in members:
            number_by_item[member.id] = number
    return Bom(rows=rows, bmk_by_item=bmk, number_by_item=number_by_item)


def _normalize(tag: str) -> str:
    """`k1`, `-K 1` -> `-K1`; leer bleibt leer."""
    compact = re.sub(r"\s+", "", tag).upper()
    return compact if compact.startswith("-") or not compact else "-" + compact


def _first(values) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""
