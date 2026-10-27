"""Kennzahlen je Schritt aus den letzten Laeufen (rein, ohne Datenbank).

Eingabe: Laeufe, neueste zuerst. Alle Sekundenwerte sind auf eine Nachkommastelle gerundet.
"""

from statistics import mean, median

from app.ablauf.schritte import SCHRITTE, dauer_s

ZIELE: dict[str, float] = {"lesen": 60.0, "zusammenfassung": 30.0, "gesamt": 180.0}


def _erster(paare: list[tuple[str, float]]) -> float | None:
    """Wert des ersten Laufs in der Liste (neueste zuerst), None ohne Werte."""
    return paare[0][1] if paare else None


def _auswertung(
    werte: list[tuple[str, float]], letzter_s: float | None, ziel_s: float | None
) -> dict:
    """Kennzahlen aus (run_id, wert)-Paaren. Ohne Werte stehen ueberall None."""
    ueber_ziel = letzter_s is not None and ziel_s is not None and letzter_s > ziel_s
    if not werte:
        return {
            "anzahl": 0,
            "mittel_s": None,
            "median_s": None,
            "max_s": None,
            "letzter_s": None,
            "ziel_s": ziel_s,
            "ueber_ziel": False,
            "langsamster_run_id": None,
        }
    zahlen = [wert for _, wert in werte]
    max_s = max(zahlen)
    langsamster = next(run_id for run_id, wert in werte if wert == max_s)
    return {
        "anzahl": len(zahlen),
        "mittel_s": round(mean(zahlen), 1),
        "median_s": round(median(zahlen), 1),
        "max_s": round(max_s, 1),
        "letzter_s": letzter_s,
        "ziel_s": ziel_s,
        "ueber_ziel": ueber_ziel,
        "langsamster_run_id": langsamster,
    }


def _fragendauern(lauf: dict) -> list[float]:
    """Dauern aller Fragen der Zusammenfassung eines Laufs (fehlende Dauern entfallen)."""
    for schritt in lauf["steps"]:
        if schritt["key"] == "zusammenfassung":
            return [
                frage["dauer_s"]
                for frage in schritt.get("result") or []
                if frage.get("dauer_s") is not None
            ]
    return []


def kennzahlen(laeufe: list[dict]) -> dict:
    """Anzahl, Mittel, Median, Maximum, letzter Wert und Ziel je Schritt, Gesamtzeit und Fragen."""
    schritte: dict[str, dict] = {}
    for key, _ in SCHRITTE:
        pro_lauf = []
        for lauf in laeufe:
            schritt = next((s for s in lauf["steps"] if s["key"] == key), None)
            wert = dauer_s(schritt) if schritt else None
            if wert is not None:
                pro_lauf.append((lauf["id"], wert))
        schritte[key] = _auswertung(pro_lauf, _erster(pro_lauf), ZIELE.get(key))

    gesamt_pro_lauf = []
    for lauf in laeufe:
        dauern = [d for s in lauf["steps"] if (d := dauer_s(s)) is not None]
        if dauern:
            gesamt_pro_lauf.append((lauf["id"], round(sum(dauern), 1)))

    # Pro Lauf zaehlt fuer "letzter" die langsamste Frage; Mittel und Median ueber alle Fragen.
    fragen_alle = []
    fragen_pro_lauf = []
    for lauf in laeufe:
        dauern = _fragendauern(lauf)
        fragen_alle.extend((lauf["id"], d) for d in dauern)
        if dauern:
            fragen_pro_lauf.append((lauf["id"], max(dauern)))

    return {
        "schritte": schritte,
        "gesamt": _auswertung(gesamt_pro_lauf, _erster(gesamt_pro_lauf), ZIELE["gesamt"]),
        "fragen": _auswertung(fragen_alle, _erster(fragen_pro_lauf), ZIELE["zusammenfassung"]),
        "laeufe": len(laeufe),
    }
