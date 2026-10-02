"""Kennzahlen einer Maschine: Zeilen bereinigen, erste Kennzahl als Kurztext."""


def clean_specs(specs: list[dict]) -> list[dict]:
    """Felder trimmen, Zeilen ohne Bezeichnung weglassen, Reihenfolge als position."""
    rows = []
    for spec in specs:
        row = {key: str(spec.get(key) or "").strip() for key in ("label", "value", "unit", "source")}
        if row["label"]:
            rows.append({**row, "position": len(rows)})
    return rows


def key_figure(specs: list[dict]) -> str:
    """Erste Kennzahl als Kurztext fuer die Maschinenuebersicht, z. B. '2.200 m/min'."""
    if not specs:
        return ""
    first = specs[0]
    return f"{first.get('value', '')} {first.get('unit', '')}".strip()
