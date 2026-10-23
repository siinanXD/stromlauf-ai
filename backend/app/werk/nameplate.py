"""Abgleich Typenschild <-> Stueckliste (SIN-982): passt die gelesene Bestellnummer zur Stuecklistenzeile des Bauteils?

Reine Logik ohne Datenbank und Modell. Verglichen wird ohne Leerzeichen, Striche, Punkte und Gross/Klein
(`3RT2026-1BB40` = `3RT2026 1BB40`). Fehlt Schild oder Zeile, bleibt das Ergebnis „unklar“, nie „passt“.
"""

import re

PASST = "passt"
WEICHT_AB = "weicht ab"
UNKLAR = "unklar"

_SEPARATORS = re.compile(r"[\s\-./_]+")
MIN_ORDER_LEN = 4  # kuerzere Nummern sind zu unspezifisch fuer einen Teiltreffer


def _squash(text: str) -> str:
    return _SEPARATORS.sub("", text).upper()


def compare(plate: dict, bom_line: str | None) -> dict:
    """`plate`: manufacturer, order_number, type; `bom_line`: Text der Stuecklistenzeile oder None.

    Ergebnis: status (passt | weicht ab | unklar), reason als Satz, order_number_found, manufacturer_found."""
    order = _squash(plate.get("order_number") or "")
    maker = _squash(plate.get("manufacturer") or "")
    if not bom_line or not bom_line.strip():
        return _result(UNKLAR, "Keine Stücklistenzeile zu diesem Bauteil.", None, None)
    if len(order) < MIN_ORDER_LEN:
        return _result(UNKLAR, "Auf dem Typenschild ist keine Bestellnummer lesbar.", None, None)
    line = _squash(bom_line)
    maker_found = (maker in line) if maker else None
    if order in line:
        return _result(PASST, "Die Bestellnummer steht in der Stücklistenzeile.", True, maker_found)
    return _result(
        WEICHT_AB, "Die Bestellnummer vom Typenschild steht nicht in der Stücklistenzeile.", False, maker_found
    )


def _result(status: str, reason: str, order_found: bool | None, maker_found: bool | None) -> dict:
    return {"status": status, "reason": reason, "order_number_found": order_found, "manufacturer_found": maker_found}
