"""Vorkalkulation: Auftrag -> Termin, Zeitplan je Station, Materialbedarf, Kosten. Ohne Datenbank.

Ablauf: Buero-Stationen nacheinander (Buerokalender) -> Eigenfertigung des Rohpapiers je Position
nacheinander auf der Papiermaschine -> je Position die Linie (gekoppelte Schritte laufen gleichzeitig,
Dauer = laengste Ruestzeit + Menge / Engpass; gleiche Linie nacheinander, andere Linien parallel) ->
Verladung (LKW = Paletten / Kapazitaet, Runden = LKW / Tore). Freie Kapazitaet, Rohstoffe vorraetig.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from app.werk.calendar import ALWAYS, Window, add_work, closed_spans, next_open

PAPER = "ROHPAPIER"


@dataclass
class Step:
    machine_id: str
    machine_name: str
    line: str
    rate: float
    rate_unit: str = "unit_min"  # unit_min (Einheiten/min) | pallet_h (Paletten/h)
    setup_min: float = 0.0
    coupled: bool = True  # laeuft gleichzeitig mit dem vorigen Schritt
    hourly_rate: float | None = None  # Maschinenstundensatz EUR/h
    basis: str = ""


@dataclass
class BomLine:
    material_code: str
    qty: float
    per: str = "unit"  # unit | pallet; bei Material-Eltern: je 1 Einheit des Elternmaterials


@dataclass
class Article:
    id: str
    code: str
    name: str
    unit_name: str
    units_per_pallet: int
    sheets_per_unit: int
    sheet_w_mm: float
    sheet_l_mm: float
    plies: int
    gsm: float
    waste_pct: float
    line: str
    routing: list[Step] = field(default_factory=list)
    bom: list[BomLine] = field(default_factory=list)


@dataclass
class Maker:
    """Eigenfertigung eines Materials: Maschine, Leistung in Materialeinheit je Stunde, Stundensatz."""

    machine_id: str
    machine_name: str
    rate_per_h: float
    hourly_rate: float | None = None


@dataclass
class Material:
    code: str
    name: str
    unit: str
    price: float | None = None  # EUR je Einheit (Zukauf)
    price_source: str = ""
    made_on: Maker | None = None
    bom: list[BomLine] = field(default_factory=list)


@dataclass
class OfficeStep:
    key: str
    label: str
    minutes: float
    min_pallets: int = 0  # nur ab dieser Palettenzahl (z. B. Freigabe Geschaeftsfuehrung)


@dataclass
class Settings:
    office: Window
    production: Window
    shipping: Window
    office_steps: list[OfficeStep]
    office_rate: float | None
    truck_capacity: int
    load_min: float
    docks: int
    dock_rate: float | None


@dataclass
class Position:
    article: Article
    quantity: float
    unit: str = "unit"  # unit | pallet


# --- Hilfen ---------------------------------------------------------------------------------------


def parse_number(text: str) -> float | None:
    """Deutsche Zahl aus einer Kennzahl: '1.500' -> 1500, '2,8' -> 2.8, '~30.000' -> 30000; sonst None."""
    cleaned = str(text).strip().lstrip("~≈ca. ").strip()
    if not re.fullmatch(r"\d{1,3}(\.\d{3})*(,\d+)?|\d+(,\d+)?", cleaned):
        return None
    return float(cleaned.replace(".", "").replace(",", "."))


def de(value: float, digits: int = 0) -> str:
    """Zahl deutsch formatiert: 10000 -> '10.000', 0.7268 (3) -> '0,727'."""
    text = f"{value:,.{digits}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def duration(minutes: float) -> str:
    hours, rest = divmod(round(minutes), 60)
    return f"{hours} h {rest:02d} min" if hours else f"{rest} min"


def iso(t: datetime) -> str:
    return t.isoformat(timespec="minutes")


def paper_kg_per_unit(article: Article) -> float:
    """Blatt x Blattflaeche x Lagen x g/m2 x (1 + Verschnitt)."""
    area_m2 = article.sheets_per_unit * article.sheet_w_mm / 1000 * article.sheet_l_mm / 1000
    return area_m2 * article.plies * article.gsm / 1000 * (1 + article.waste_pct / 100)


def _units(position: Position) -> int:
    if position.quantity <= 0:
        raise ValueError(f"Menge fuer {position.article.name} muss groesser als 0 sein")
    if position.unit == "pallet":
        return math.ceil(position.quantity * position.article.units_per_pallet)
    if position.unit == "unit":
        return math.ceil(position.quantity)
    raise ValueError(f"Einheit muss 'unit' oder 'pallet' sein, nicht {position.unit!r}")


def _units_per_min(step: Step, units_per_pallet: int) -> float:
    return step.rate * units_per_pallet / 60 if step.rate_unit == "pallet_h" else step.rate


def _groups(routing: list[Step]) -> list[list[Step]]:
    groups: list[list[Step]] = []
    for step in routing:
        if groups and step.coupled:
            groups[-1].append(step)
        else:
            groups.append([step])
    return groups


# --- Material -------------------------------------------------------------------------------------


def _explode(position_units: int, pallets: int, article: Article, materials: dict[str, Material]) -> dict:
    """Bedarf einer Position: {code: {qty, basis, level, parent}} inkl. Rezepturen der Eigenfertigung."""
    need: dict[str, dict] = {}

    def add(code: str, qty: float, basis: str, level: int, parent: str | None) -> None:
        entry = need.setdefault(code, {"qty": 0.0, "basis": [], "level": level, "parent": parent})
        entry["qty"] += qty
        entry["basis"].append(basis)

    if PAPER in materials:
        kg = paper_kg_per_unit(article)
        add(PAPER, position_units * kg / 1000, f"{de(kg, 3)} kg × {de(position_units)}", 0, None)
    for line in article.bom:
        count = position_units if line.per == "unit" else pallets
        per = "Palette" if line.per == "pallet" else article.unit_name
        add(line.material_code, line.qty * count, f"{de(line.qty, 3).rstrip('0').rstrip(',')} je {per} × {de(count)}", 0, None)

    def expand(code: str, qty: float, depth: int) -> None:
        material = materials.get(code)
        if material is None or not material.bom:
            return
        if depth > 5:
            raise ValueError(f"Rezeptur von {code} ist zu tief verschachtelt (Kreis?)")
        for line in material.bom:
            add(line.material_code, qty * line.qty, f"{de(line.qty, 3).rstrip('0').rstrip(',')} je {material.unit} {material.name}", depth + 1, code)
            expand(line.material_code, qty * line.qty, depth + 1)

    for code, entry in list(need.items()):
        expand(code, entry["qty"], 0)
    return need


# --- Kalkulation ----------------------------------------------------------------------------------


def calculate(
    received_at: datetime,
    due: date | None,
    positions: list[Position],
    materials: dict[str, Material],
    settings: Settings,
) -> dict:
    if not positions:
        raise ValueError("Auftrag ohne Positionen")
    warnings: list[str] = []
    units = [_units(p) for p in positions]
    pallets = [math.ceil(u / p.article.units_per_pallet) for u, p in zip(units, positions, strict=True)]
    total_pallets = sum(pallets)
    stations: list[dict] = []

    def station(key, label, group, start, end, minutes, calendar, basis, **extra) -> dict:
        item = {
            "key": key, "label": label, "group": group, "start": iso(start), "end": iso(end),
            "work_minutes": minutes, "calendar": calendar, "basis": basis, "bottleneck": None,
            "machines": [], "position": None, **extra,
        }
        stations.append(item)
        return item

    # Buero
    t = received_at
    office_minutes = 0.0
    for step in settings.office_steps:
        if total_pallets < step.min_pallets:
            continue
        end = add_work(t, step.minutes, settings.office)
        note = f"{duration(step.minutes)} Bearbeitung" + (f", ab {step.min_pallets} Paletten" if step.min_pallets else "")
        station(f"office:{step.key}", step.label, "Büro", next_open(t, settings.office), end, step.minutes, "office", note)
        office_minutes += step.minutes
        t = end
    released = t

    # Material je Position und Eigenfertigung des Rohpapiers
    needs = [_explode(u, pal, p.article, materials) for u, pal, p in zip(units, pallets, positions, strict=True)]
    paper = materials.get(PAPER)
    if paper is None:
        warnings.append("Material ROHPAPIER fehlt in den Stammdaten: ohne Papierbedarf gerechnet")
    elif paper.made_on is None:
        warnings.append("Rohpapier hat keine Eigenfertigung: Papier gilt als vorrätig")
    maker_free = released
    ready: list[datetime] = []
    make_minutes: list[float] = []
    for index, need in enumerate(needs):
        paper_t = need.get(PAPER, {"qty": 0.0})["qty"]
        if paper is None or paper.made_on is None or paper_t <= 0:
            ready.append(released)
            make_minutes.append(0.0)
            continue
        maker = paper.made_on
        minutes = paper_t / maker.rate_per_h * 60
        start = next_open(maker_free, settings.production)
        end = add_work(maker_free, minutes, settings.production)
        station(
            f"make:{index}", maker.machine_name, "Rohpapier", start, end, minutes, "production",
            f"{de(paper_t, 2)} t ÷ {de(maker.rate_per_h, 1)} t/h = {duration(minutes)}",
            machines=[maker.machine_name], position=index,
        )
        maker_free = end
        ready.append(end)
        make_minutes.append(minutes)

    # Linien
    line_free: dict[str, datetime] = {}
    ends: list[datetime] = []
    line_costs: list[float] = []
    missing_rates: set[str] = set()
    summary_line_minutes = 0.0
    longest: tuple[float, str] = (0.0, "")
    for index, position in enumerate(positions):
        article = position.article
        t = ready[index]
        cost = 0.0
        groups = _groups(article.routing)
        if not groups:
            warnings.append(f"Kein Arbeitsplan für {article.name}: ohne Fertigungszeit gerechnet")
        for g, group in enumerate(groups):
            rates = [(_units_per_min(s, article.units_per_pallet), s) for s in group]
            rate, bottleneck = min(rates, key=lambda item: item[0])
            setup = max(s.setup_min for s in group)
            minutes = setup + units[index] / rate
            key = group[0].line or group[0].machine_id
            begin = max(t, line_free.get(key, t))
            start = next_open(begin, settings.production)
            end = add_work(begin, minutes, settings.production)
            line_free[key] = end
            station(
                f"line:{index}:{g}", group[0].line or group[0].machine_name, group[0].line or "Fertigung",
                start, end, minutes, "production",
                f"Rüsten {duration(setup)} + {de(units[index])} {article.unit_name} ÷ "
                f"{de(rate, 1)} je min (Engpass {bottleneck.machine_name}) = {duration(minutes)}",
                bottleneck=bottleneck.machine_name, machines=[s.machine_name for s in group], position=index,
            )
            for s in group:
                if s.hourly_rate is None:
                    missing_rates.add(s.machine_name)
                else:
                    cost += minutes / 60 * s.hourly_rate
            summary_line_minutes += minutes
            longest = max(longest, (minutes, bottleneck.machine_name))
            t = end
        ends.append(t)
        line_costs.append(cost)

    # Verladung
    trucks = math.ceil(total_pallets / settings.truck_capacity)
    rounds = math.ceil(trucks / settings.docks)
    load_minutes = rounds * settings.load_min
    after = max(ends)
    ship_start = next_open(after, settings.shipping)
    ready_at = add_work(after, load_minutes, settings.shipping)
    station(
        "ship", "Verladung", "Versand", ship_start, ready_at, load_minutes, "shipping",
        f"{de(total_pallets)} Paletten ÷ {settings.truck_capacity} = {trucks} LKW; "
        f"{rounds} Runde(n) à {duration(settings.load_min)} an {settings.docks} Toren",
    )

    # Material gesamt
    merged: dict[str, dict] = {}
    for need in needs:
        for code, entry in need.items():
            item = merged.setdefault(code, {"qty": 0.0, "basis": [], "level": entry["level"], "parent": entry["parent"]})
            item["qty"] += entry["qty"]
            item["basis"] += entry["basis"]
    material_rows = []
    for code, entry in _ordered(merged):
        material = materials.get(code)
        purchased = material is not None and material.made_on is None
        price = material.price if material else None
        if material is None:
            warnings.append(f"Material {code} fehlt in den Stammdaten")
        elif purchased and price is None:
            warnings.append(f"Preis fehlt für {material.name}")
        material_rows.append({
            "code": code,
            "name": material.name if material else code,
            "unit": material.unit if material else "",
            "qty": entry["qty"],
            "level": entry["level"],
            "parent": entry["parent"],
            "basis": " + ".join(entry["basis"]),
            "price": price if purchased else None,
            "price_source": material.price_source if material else "",
            "cost": entry["qty"] * (price or 0) if purchased else 0.0,
            "made": not purchased and material is not None,
        })

    # Kosten
    for name in sorted(missing_rates):
        warnings.append(f"Maschinenstundensatz fehlt für {name}: Fertigung dort mit 0 € gerechnet")
    maker_rate = paper.made_on.hourly_rate if paper and paper.made_on else None
    if paper and paper.made_on and maker_rate is None:
        warnings.append(f"Maschinenstundensatz fehlt für {paper.made_on.machine_name}: Rohpapier ohne Fertigungskosten")
    office_cost = office_minutes / 60 * (settings.office_rate or 0)
    shipping_cost = trucks * settings.load_min / 60 * (settings.dock_rate or 0)
    cost_rows = []
    for index, position in enumerate(positions):
        material_cost = 0.0
        for code, entry in needs[index].items():
            material = materials.get(code)
            if material is not None and material.made_on is None:
                material_cost += entry["qty"] * (material.price or 0)
        production = line_costs[index] + make_minutes[index] / 60 * (maker_rate or 0)
        share = pallets[index] / total_pallets
        total = material_cost + production + (office_cost + shipping_cost) * share
        cost_rows.append({
            "article": position.article.name, "units": units[index], "unit_name": position.article.unit_name,
            "material": material_cost, "production": production, "office": office_cost * share,
            "shipping": shipping_cost * share, "total": total, "per_unit": total / units[index],
        })
    totals = {key: sum(row[key] for row in cost_rows) for key in ("material", "production", "office", "shipping", "total")}

    days_delta = (due - ready_at.date()).days if due else None
    paper_total = merged.get(PAPER, {"qty": 0.0})["qty"]
    return {
        "received_at": iso(received_at),
        "due_date": due.isoformat() if due else None,
        "ready_at": iso(ready_at),
        "meets_due": days_delta >= 0 if due else None,
        "days_delta": days_delta,
        "summary": {
            "units": sum(units),
            "pallets": total_pallets,
            "trucks": trucks,
            "paper_t": paper_total,
            "line_minutes": summary_line_minutes,
            "bottleneck": longest[1] or None,
            "lead_minutes": (ready_at - received_at).total_seconds() / 60,
        },
        "stations": stations,
        "closed": {
            key: [[iso(a), iso(b)] for a, b in closed_spans(received_at, ready_at, window)]
            for key, window in (("office", settings.office), ("production", settings.production), ("shipping", settings.shipping))
            if window != ALWAYS
        },
        "positions": [
            {
                "article_id": p.article.id, "article": p.article.name, "code": p.article.code,
                "unit_name": p.article.unit_name, "units": units[i], "pallets": pallets[i],
                "paper_kg_per_unit": paper_kg_per_unit(p.article), "ready": iso(ends[i]),
            }
            for i, p in enumerate(positions)
        ],
        "materials": material_rows,
        "costs": {"positions": cost_rows, "total": totals, "office_minutes": office_minutes, "trucks": trucks},
        "warnings": warnings,
    }


def _ordered(merged: dict[str, dict]) -> list[tuple[str, dict]]:
    """Direkter Bedarf in Reihenfolge, Rezepturbestandteile direkt unter ihrem Elternmaterial."""
    result: list[tuple[str, dict]] = []

    def visit(parent: str | None) -> None:
        for code, entry in merged.items():
            if entry["parent"] == parent:
                result.append((code, entry))
                visit(code)

    visit(None)
    return result
