"""Kennbuchstaben je Ausgabe (Issue #99): aeltere Lesart, IEC 81346-2:2019 oder offen.

Dieselben Buchstaben bedeuten je nach Ausgabe etwas anderes. In aelteren Plaenen (DIN 40719-2, franzoesische Paare wie
in QElectroTech) ist K das Schuetz, H die Meldeleuchte, U der Umrichter und Y das Ventil. Nach IEC 81346-2:2019
verarbeitet K Signale, das Schuetz steht unter Q, H behandelt Stoffe und U haelt andere Objekte; A ist nicht mehr
zulaessig, D, J, L, V, Y und Z sind reserviert. Welche Lesart gilt, bestimmt detect_edition je Quelle aus deren
Kennzeichen. Bleibt sie offen, bekommen Buchstaben mit widerspruechlicher Bedeutung keine Art, statt geraten zu werden.

Als Beleg zaehlen nur frei zugaengliche Primaerquellen, abgerufen am 01.10.2026, die Bedeutungen stehen in eigenen
Worten: die IEC-Leseprobe 81346-2:2019 (Tabelle 1 und die Unterklassen von B und C), das IHK/PAL-Merkblatt zur
DIN EN IEC 81346-2:2020-10 und fuer FC ein Siemens-Datenblatt. Nur sekundaer belegte Unterklassen zaehlen nicht und
bleiben bei der Hauptklasse. Recherche: .ai/research/2026-10-01-iec81346-2-kennbuchstaben.md
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

ALT = "alt"
NEU = "2019"
OFFEN = "offen"

# Aeltere Lesart (DIN 40719-2), Art fuer Icon und Filter im Modell
KIND_OLD = {
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
KIND_FRENCH = {
    "QF": "Schutz",
    "FU": "Schutz",
    "KM": "Schuetz/Relais",
    "KA": "Schuetz/Relais",
    "KE": "Schuetz/Relais",
    "EV": "Ventil",
    "SB": "Taster",
    "HL": "Meldung",
}
# IEC 81346-2:2019, Tabelle 1. A gibt es nur bis zur Ausgabe 2009 (zwei oder mehr Zwecke) und bleibt Baugruppe.
KIND_2019 = {
    "A": "Baugruppe",
    "B": "Sensor",
    "C": "Speicher",
    "E": "Heizung/Leuchte",
    "F": "Schutz",
    "G": "Versorgung",
    "H": "Stoffbehandlung",
    "K": "Relais/SPS",
    "M": "Antrieb",
    "N": "Abdeckung",
    "P": "Anzeige",
    "Q": "Schütz/Schalter",
    "R": "Begrenzer",
    "S": "Bedienelement",
    "T": "Umformer",
    "U": "Halterung",
    "W": "Leitung",
    "X": "Klemme",
}
# Primaer belegte Unterklassen 2019: B und C aus der IEC-Leseprobe, die Paare ab FC aus dem IHK/PAL-Merkblatt bzw.
# FC aus dem Siemens-Datenblatt. Wo die Unterklasse die Art schaerfer fasst als die Hauptklasse, steht sie in
# KIND_2019_SUB.
SUBCLASSES_2019 = frozenset(
    "BA BB BC BD BE BF BG BH BJ BK BL BM BP BQ BR BS BT BU BW BX BY BZ "
    "CA CB CC CF CL CM CN CP CQ "
    "FC KF KH MB MM QA QM RN SG SH SJ".split()
)
KIND_2019_SUB = {
    "FC": "Sicherung",
    "KH": "Fluidsteuerung",
    "MB": "Elektromagnet",
    "MM": "Zylinder",
    "QA": "Schütz/Leistungsschalter",
    "QM": "Ventil",
    "RN": "Drossel",
    "SG": "Handschalter",
    "SH": "Fußschalter",
    "SJ": "Taster",
}
NOT_2019 = frozenset("ADJLVYZ")  # 2019 nicht zulaessig (A) oder reserviert
# Paare, die IEC 81346-2 nicht kennt: Hinweis auf die franzoesische Lesart (nur sekundaer belegt, daher kein
# Gegenbeweis zu 2019, sondern Beleg fuer die aeltere Lesart, die ohnehin gilt, wenn nichts dagegen spricht)
FRENCH_ONLY = frozenset({"QF", "KM", "KA", "SB", "FU"})
# Buchstaben, die in beiden Lesarten dasselbe meinen; bei offener Lesart behalten nur sie ihre Art
SAME_IN_BOTH = frozenset("BCEFGMPRSTWX")
_NOT_PARTS = {"", "Leitung", "Klemme"}

VERB_BY_KIND = {
    "Schutz": "schützt",
    "Schalter": "schützt",
    "Sicherung": "schützt",
    "Schuetz/Relais": "schaltet",
    "Schütz/Schalter": "schaltet",
    "Schütz/Leistungsschalter": "schaltet",
    "Baugruppe": "steuert",
    "Relais/SPS": "steuert",
    "Versorgung": "versorgt",
    "Trafo": "versorgt",
    "Umrichter": "versorgt",
    "Umformer": "versorgt",
    "Klemme": "verbindet",
}

# [=Anlage][+Ort]-Kennbuchstaben, auch Blatt-Stil ohne Minus (9K1) und blanker Buchstabe
_TAG = re.compile(r"^(?:=[\w.]+)?(?:\+[\w-]+)?(?P<dash>-)?(?P<folio>\d{0,2})(?P<letters>[A-Z]{1,3})")


@dataclass(frozen=True)
class Edition:
    name: str  # alt | 2019 | offen
    reason: str


def _letters(tag: str) -> re.Match | None:
    return _TAG.match(tag.upper())


def detect_edition(tags: Iterable[str]) -> Edition:
    """Lesart einer Quelle aus ihren Kennzeichen. Fuer 2019 sprechen primaer belegte Unterklassen und die dritte
    Buchstabenebene, fuer die aeltere Lesart Buchstaben, die 2019 nicht zulaessig oder reserviert sind, franzoesische
    Paare und Kennzeichen ohne Minus im Blatt-Stil. Eine Seite gewinnt nur mit mindestens doppelt so vielen
    Kennzeichen wie die andere; sonst und ohne jeden Hinweis bleibt die Lesart offen."""
    new: list[str] = []
    old: list[str] = []
    for tag in dict.fromkeys(t.strip().upper() for t in tags if t and t.strip()):
        match = _letters(tag)
        if match is None:
            continue
        letters = match["letters"]
        if not match["dash"]:
            if match["folio"]:
                old.append(tag)  # Blatt-Stil (4Q1) ist QElectroTech-Praxis, kein Kennzeichen nach IEC 81346
            continue
        if letters[0] in NOT_2019 or letters[:2] in FRENCH_ONLY:
            old.append(tag)
        elif len(letters) == 3 or letters[:2] in SUBCLASSES_2019:
            new.append(tag)

    def sample(found: list[str]) -> str:
        return ", ".join(found[:3])

    if new and len(new) >= 2 * len(old):
        return Edition(NEU, f"{len(new)} Kennzeichen mit Unterklassen nach IEC 81346-2:2019, z. B. {sample(new)}")
    if old and len(old) >= 2 * len(new):
        return Edition(ALT, f"{len(old)} Kennzeichen nach aelterer Lesart, z. B. {sample(old)}")
    if new or old:
        return Edition(
            OFFEN, f"widerspruechlich: {len(new)} nach 2019 ({sample(new)}), {len(old)} nach aelterer Lesart ({sample(old)})"
        )
    return Edition(OFFEN, "nur Kennbuchstaben, die in beiden Lesarten vorkommen")


def kind_of(tag: str, edition: str = ALT) -> str:
    """Art eines Betriebsmittels in der Lesart der Quelle; leer, wenn der Buchstabe nichts Sicheres sagt."""
    match = _letters(tag)
    if match is None:
        return ""
    letters = match["letters"]
    if edition == NEU:
        return KIND_2019_SUB.get(letters[:2]) or KIND_2019.get(letters[0], "")
    if edition == OFFEN:
        if letters[:2] in KIND_FRENCH:
            return ""  # KE, EV, HL: franzoesisch und nach 2019 Verschiedenes
        return KIND_OLD.get(letters[0], "") if letters[0] in SAME_IN_BOTH else ""
    return KIND_FRENCH.get(letters[:2]) or KIND_OLD.get(letters[0], "")


def is_part(tag: str, edition: str = ALT) -> bool:
    """Betriebsmittel des Modells: Kennbuchstabe bekannt, keine Leitung, keine Klemme. Bei offener Lesart reicht eine
    der beiden Lesarten, sonst fiele -K1 heraus, nur weil seine Art offen ist."""
    editions = (ALT, NEU) if edition == OFFEN else (edition,)
    return any(kind_of(tag, name) not in _NOT_PARTS for name in editions)


def verb_of(kind: str) -> str:
    """Beziehung zu einem verbundenen Bauteil aus dessen Art (Bauteil-Sheet)."""
    return VERB_BY_KIND.get(kind, "hängt an")
