"""Ordnet eine Datei ohne Anlage der aehnlichsten Gruppe zu (Cosinus-Aehnlichkeit).

Rein: kein Datenbankzugriff, kein Modellaufruf. Die Vektoren kommen vom Aufrufer (Chunk-Embeddings),
die Ausgabe ist ein Vorschlag fuer den Nutzer. Nie raten: unter der Schwelle oder bei knappem
Abstand zur zweitbesten Gruppe bleibt die Datei unzugeordnet.
"""

import math
from collections.abc import Mapping, Sequence

# Mindestabstand zwischen bester und zweitbester Gruppe. Die Einstellung heisst
# `ABLAUF_AEHNLICHKEIT_ABSTAND` (config.py); der Aufrufer reicht sie durch.
ABSTAND = 0.05


def _normiert(vektor: Sequence[float]) -> list[float]:
    """Einheitsvektor. Wirft `ValueError` bei leerem Vektor, Nullvektor und nicht endlichen Werten."""
    if not vektor:
        raise ValueError("Leerer Vektor")
    if not all(math.isfinite(x) for x in vektor):
        raise ValueError("Vektor enthaelt nan oder inf")
    laenge = math.sqrt(sum(x * x for x in vektor))
    if laenge == 0.0:
        raise ValueError("Nullvektor hat keine Richtung")
    return [x / laenge for x in vektor]


def mittelwert_vektor(vektoren: Sequence[Sequence[float]]) -> list[float]:
    """Normierter Mittelwert mehrerer Vektoren, z. B. der Chunk-Vektoren einer Gruppe.

    Eingabe: Vektoren gleicher Laenge. Ausgabe: Einheitsvektor in Richtung des Mittels.
    Wirft `ValueError` bei leerer Liste, verschiedenen Laengen oder wenn sich die Vektoren
    zu Null aufheben.
    """
    if not vektoren:
        raise ValueError("Mittelwert braucht mindestens einen Vektor")
    laenge = len(vektoren[0])
    if any(len(v) != laenge for v in vektoren):
        raise ValueError("Vektoren haben verschiedene Laengen")
    summe = [sum(spalte) for spalte in zip(*vektoren, strict=True)]
    return _normiert(summe)


def ordne_zu(
    datei_vektor: Sequence[float],
    gruppen_vektoren: Mapping[str, Sequence[float]],
    schwelle: float,
    abstand: float = ABSTAND,
) -> tuple[str | None, float]:
    """Gruppe mit dem hoechsten Cosinus zur Datei, sonst `None`.

    Eingabe: Vektor der Datei, `{gruppenname: Vektor}` (etwa aus `mittelwert_vektor`),
    `schwelle` (Cosinus, ab dem zugeordnet wird, inklusive) und `abstand` (Mindestabstand der
    besten zwei Gruppen, exklusive).
    Ausgabe: `(gruppe, wert)` bei Treffer, sonst `(None, bester_wert)`. Ohne Gruppen `(None, 0.0)`.
    Wirft `ValueError` bei Nullvektor, nicht endlichen Werten oder verschiedenen Laengen.
    """
    datei = _normiert(datei_vektor)
    werte: list[tuple[float, str]] = []
    for name, vektor in gruppen_vektoren.items():
        if len(vektor) != len(datei):
            raise ValueError(f"Gruppe {name!r}: Vektorlaenge {len(vektor)} statt {len(datei)}")
        gruppe = _normiert(vektor)
        werte.append((sum(a * b for a, b in zip(datei, gruppe, strict=True)), name))
    if not werte:
        return None, 0.0

    werte.sort(key=lambda eintrag: eintrag[0], reverse=True)
    bester_wert, bester_name = werte[0]
    if bester_wert < schwelle:
        return None, bester_wert
    if len(werte) > 1 and bester_wert - werte[1][0] < abstand:
        return None, bester_wert
    return bester_name, bester_wert
