"""Standortplan: Lage der Hallen, Materialfluss zwischen Hallen, Kennzahlen der Maschinen."""

HALL_KINDS = ("generic", "base", "production", "warehouse", "office")

# Standardlage fuer Hallen ohne Rechteck: Reihen zu drei Bloecken
MARGIN = 40
GAP = 60
DEFAULT_W = 360
DEFAULT_H = 260
PER_ROW = 3

GATE_LABEL = "Anzahl Tore"
MAX_DOCKS = 50  # Tippfehler wie 88888888 sollen den Plan nicht einfrieren

Rect = tuple[float, float, float, float]


def place_halls(rects: list[Rect]) -> list[Rect]:
    """Hallen ohne Groesse bekommen eine Lage unterhalb der schon platzierten Hallen."""
    placed = [r for r in rects if r[2] > 0 and r[3] > 0]
    top = max((y + h + GAP for _, y, _, h in placed), default=MARGIN)
    result, index = [], 0
    for rect in rects:
        if rect in placed:
            result.append(rect)
            continue
        row, column = divmod(index, PER_ROW)
        x = MARGIN + column * (DEFAULT_W + GAP)
        y = top + row * (DEFAULT_H + GAP)
        result.append((x, y, DEFAULT_W, DEFAULT_H))
        index += 1
    return result


def check_site_flows(flows: list[tuple[str, str]], hall_ids: set[str]) -> None:
    seen: set[tuple[str, str]] = set()
    for source, target in flows:
        if source == target:
            raise ValueError("Ein Fluss braucht zwei verschiedene Hallen")
        if source not in hall_ids or target not in hall_ids:
            raise ValueError("Fluss verweist auf eine unbekannte Halle")
        if (source, target) in seen:
            raise ValueError("Fluss doppelt angegeben")
        seen.add((source, target))


def clean_specs(specs: list[dict]) -> list[dict]:
    """Felder trimmen, Zeilen ohne Bezeichnung weglassen, Reihenfolge als position."""
    rows = []
    for spec in specs:
        row = {key: str(spec.get(key) or "").strip() for key in ("label", "value", "unit", "source")}
        if row["label"]:
            rows.append({**row, "position": len(rows)})
    return rows


def key_figure(specs: list[dict]) -> str:
    """Erste Kennzahl als Kurztext fuer die Kachel, z. B. '2.200 m/min'."""
    if not specs:
        return ""
    first = specs[0]
    return f"{first.get('value', '')} {first.get('unit', '')}".strip()


def dock_count(specs: list[dict]) -> int:
    """Summe der Kennzahlen 'Anzahl Tore' (nur ganze Zahlen), hoechstens MAX_DOCKS."""
    total = sum(
        int(value)
        for spec in specs
        if spec.get("label") == GATE_LABEL
        and (value := str(spec.get("value", "")).strip()).isdecimal()
    )
    return min(total, MAX_DOCKS)
