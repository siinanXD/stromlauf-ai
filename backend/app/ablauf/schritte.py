"""Zustandsmaschine der sieben Ablauf-Schritte (rein, ohne Datenbank).

Jede Funktion gibt eine neue Liste zurueck. Die Eingabe bleibt unveraendert.
"""

from datetime import datetime

SCHRITTE: list[tuple[str, str]] = [
    ("hochladen", "Hochladen"),
    ("lesen", "Lesen"),
    ("maschine", "Maschine anlegen"),
    ("steckbrief", "Steckbrief"),
    ("modell", "Maschinenmodell"),
    ("zusammenfassung", "Zusammenfassung"),
    ("fertig", "Fertig"),
]


def neue_schritte() -> list[dict]:
    """Alle sieben Schritte im Zustand 'wartet'."""
    return [
        {
            "key": key,
            "label": label,
            "status": "wartet",
            "started_at": None,
            "finished_at": None,
            "input": "",
            "output": "",
            "trace_url": None,
            "error": None,
        }
        for key, label in SCHRITTE
    ]


def _aendere(steps: list[dict], key: str, **felder) -> list[dict]:
    """Kopie der Liste, in der der Schritt mit `key` die `felder` erhaelt."""
    return [{**s, **felder} if s["key"] == key else dict(s) for s in steps]


def starte(steps: list[dict], key: str, now: str, input: str) -> list[dict]:
    """Schritt auf 'laeuft' setzen, Start und Eingabe merken."""
    return _aendere(steps, key, status="laeuft", started_at=now, input=input)


def beende(steps: list[dict], key: str, now: str, output: str) -> list[dict]:
    """Schritt auf 'fertig' setzen, Ende und Ausgabe merken."""
    return _aendere(steps, key, status="fertig", finished_at=now, output=output)


def scheitere(steps: list[dict], key: str, now: str, error: str) -> list[dict]:
    """Schritt auf 'fehler' setzen. Die uebrigen Schritte bleiben unveraendert."""
    return _aendere(steps, key, status="fehler", finished_at=now, error=error)


def lauf_status(steps: list[dict]) -> str:
    """Gesamtstatus: 'fehler', sobald ein Schritt fehlschlaegt, 'fertig' wenn alle fertig sind."""
    stati = {s["status"] for s in steps}
    if "fehler" in stati:
        return "fehler"
    if stati == {"fertig"}:
        return "fertig"
    return "laeuft"


def dauer_s(step: dict) -> float | None:
    """Dauer des Schritts in Sekunden (eine Nachkommastelle), None solange Start oder Ende fehlt."""
    if not step["started_at"] or not step["finished_at"]:
        return None
    start = datetime.fromisoformat(step["started_at"])
    ende = datetime.fromisoformat(step["finished_at"])
    return round((ende - start).total_seconds(), 1)
