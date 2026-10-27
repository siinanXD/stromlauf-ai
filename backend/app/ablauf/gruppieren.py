"""Gruppiert abgelegte Dateien zu Anlagen: erst nach Unterordner, dann nach Kennung.

Rein: keine Dateizugriffe, keine Netzwerkaufrufe. Die Eingabe kommt vom Upload
(Name und Pfad relativ zum abgelegten Ordner), die Ausgabe ist Vorschlag fuer den Nutzer.
"""

import re
from pathlib import PurePosixPath

from app.api.sources import ALLOWED_SUFFIXES

# Kennung: 2-4 Grossbuchstaben, optional eine Ziffer, Bindestrich, 1-3 Buchstaben/Ziffern.
# Gilt nur als ganzes Wort (Klammer, Unterstrich, Leerzeichen oder Namensende davor/danach).
KENNUNG = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,4}\d?)-[A-Za-z0-9]{1,3}(?![A-Za-z0-9])")

# Praefixe, die nie eine Anlagenkennung sind (Sprachen, Normen, Dateiformate, Revisionen).
KEINE_KENNUNG = frozenset(
    "DE EN US FR IT ES NL PL UTF REV IP PDF DIN ISO IEC VDE EOL SPS PLC AWL FUP SCL CAD DXF".split()
)


def _kennung_roh(name: str) -> str | None:
    """Erste Kennung im Dateinamen (ohne Endung), in Originalschreibweise."""
    stamm = PurePosixPath(name).stem
    for treffer in KENNUNG.finditer(stamm):
        if treffer.group(1) not in KEINE_KENNUNG:
            return treffer.group(0)
    return None


def kennung_aus_name(name: str) -> str | None:
    """Normalisierte Kennung (Grossbuchstaben, ohne Bindestrich), z. B. `FB01`."""
    roh = _kennung_roh(name)
    return roh.upper().replace("-", "") if roh else None


def gruppiere(dateien: list[dict]) -> dict:
    """Ordnet Dateien Gruppen zu. Unterordner gewinnt vor Kennung.

    Eingabe: `[{"name": str, "pfad": str}]`, `pfad` relativ zum Ordner, Wurzeldateien ohne `/`.
    Ausgabe: `{"gruppen": [{"name", "quelle", "dateien"}], "unzugeordnet": [...], "ignoriert": [...]}`.
    Dateien mit nicht erlaubter Endung landen in `ignoriert`. Ein Ordner ohne erlaubte Datei
    ergibt keine Gruppe.
    """
    ordner: dict[str, list[str]] = {}
    kennungen: dict[str, tuple[str, list[str]]] = {}
    unzugeordnet: list[str] = []
    ignoriert: list[str] = []

    for datei in dateien:
        name, pfad = datei["name"], datei["pfad"]
        if PurePosixPath(name).suffix.lower() not in ALLOWED_SUFFIXES:
            ignoriert.append(pfad)
        elif "/" in pfad:
            ordner.setdefault(pfad.split("/")[0], []).append(pfad)
        else:
            roh = _kennung_roh(name)
            if roh is None:
                unzugeordnet.append(pfad)
            else:
                schluessel = roh.upper().replace("-", "")
                # Erste Fundstelle bestimmt die Anzeige-Schreibweise.
                kennungen.setdefault(schluessel, (roh, []))[1].append(pfad)

    gruppen = [
        {"name": ordner_name, "quelle": "ordner", "dateien": ordner[ordner_name]}
        for ordner_name in sorted(ordner)
    ]
    gruppen += [
        {"name": anzeige, "quelle": "kennung", "dateien": pfade}
        for _, (anzeige, pfade) in sorted(kennungen.items())
    ]
    return {"gruppen": gruppen, "unzugeordnet": unzugeordnet, "ignoriert": ignoriert}
