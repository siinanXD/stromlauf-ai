"""Stammdaten fuer die Vorkalkulation aus JSON (Testwerk-Datei, plant_settings) in Rechenkern-Objekte."""

from datetime import time

from app.werk import calc
from app.werk.calendar import ALWAYS

HOURLY_LABEL = "Maschinenstundensatz"


def hourly_rate(specs: list[dict]) -> float | None:
    """Maschinenstundensatz (EUR/h) aus den Kennzahlen einer Maschine; None, wenn fehlt oder kein Zahlwert."""
    for spec in specs:
        if spec.get("label") == HOURLY_LABEL:
            return calc.parse_number(spec.get("value", ""))
    return None


def settings_from_json(value: dict) -> calc.Settings:
    """Parameter pruefen und umwandeln; ValueError mit Klartext bei unbrauchbaren Werten."""
    calendars = value["calendars"]
    for name in ("office", "production", "shipping"):
        window = calendars[name]
        if window == ALWAYS:
            continue
        if not window.get("days"):
            raise ValueError(f"Kalender {name}: keine Arbeitstage")
        if time.fromisoformat(window["from"]) >= time.fromisoformat(window["to"]):
            raise ValueError(f"Kalender {name}: 'from' muss vor 'to' liegen")
    for key in ("truck_capacity", "docks", "load_min"):
        if not float(value[key]) > 0:
            raise ValueError(f"Parameter {key} muss größer als 0 sein")
    return calc.Settings(
        office=calendars["office"],
        production=calendars["production"],
        shipping=calendars["shipping"],
        office_steps=[
            calc.OfficeStep(s["key"], s["label"], float(s["minutes"]), int(s.get("min_pallets", 0)))
            for s in value["office_steps"]
        ],
        office_rate=value.get("office_rate"),
        truck_capacity=int(value["truck_capacity"]),
        load_min=float(value["load_min"]),
        docks=int(value["docks"]),
        dock_rate=value.get("dock_rate"),
    )


def inputs_from_werk(werk: dict) -> tuple[dict[str, calc.Article], dict[str, calc.Material], calc.Settings]:
    """Testwerk-JSON -> (Artikel je Code, Materialien je Code, Parameter). Maschinen per Schluessel."""
    machines = {m["key"]: m for hall in werk["halls"] for m in hall["machines"]}
    materials: dict[str, calc.Material] = {}
    for item in werk["materials"]:
        made = item.get("made_on")
        maker = None
        if made:
            machine = machines[made["machine"]]
            maker = calc.Maker(made["machine"], machine["name"], made["rate_per_h"], hourly_rate(machine["specs"]))
        materials[item["code"]] = calc.Material(
            item["code"], item["name"], item["unit"], item.get("price"), item.get("price_source", ""), maker,
            [calc.BomLine(line["material"], line["qty"]) for line in item["bom"]],
        )
    articles: dict[str, calc.Article] = {}
    for item in werk["articles"]:
        tech = item["tech"]
        routing = []
        for step in item["routing"]:
            machine = machines[step["machine"]]
            routing.append(calc.Step(
                step["machine"], machine["name"], machine["line"], step["rate"], step["rate_unit"],
                step["setup_min"], step["coupled"], hourly_rate(machine["specs"]), step["basis"],
            ))
        articles[item["code"]] = calc.Article(
            item["code"], item["code"], item["name"], item["unit_name"], item["units_per_pallet"],
            tech["sheets_per_unit"], tech["sheet_w_mm"], tech["sheet_l_mm"], tech["plies"], tech["gsm"],
            tech["waste_pct"], item["line"], routing,
            [calc.BomLine(line["material"], line["qty"], line["per"]) for line in item["bom"]],
        )
    return articles, materials, settings_from_json(werk["settings"]["calc"])


def sim_params(value: dict) -> tuple[dict[str, int], float]:
    """Personen je Buero-Station und Dauer einer Kreditklaerung (Minuten Buerozeit) aus den Parametern."""
    workers = {step["key"]: max(1, int(step.get("workers", 1))) for step in value["office_steps"]}
    return workers, float(value.get("credit_hold_min", 540))


def sim_inputs_from_werk(werk: dict, articles: dict[str, calc.Article]):
    """Testwerk-JSON -> (Auftraege, Bestand je Code, Preise je Code, Personen, Klaerungsdauer)."""
    from datetime import date, datetime

    from app.werk.sim import Customer, SimLine, SimOrder

    customers = {c["name"]: Customer(c["name"], c["name"], float(c["credit_limit"])) for c in werk["customers"]}
    orders = [
        SimOrder(
            o["number"], o["number"], customers[o["customer"]], datetime.fromisoformat(o["received_at"]),
            date.fromisoformat(o["due_date"]) if o.get("due_date") else None,
            [SimLine(articles[line["article"]], line["quantity"], line["unit"]) for line in o["lines"]],
        )
        for o in werk["orders"]
    ]
    stock = {s["article"]: int(s["units"]) for s in werk["stock"]}
    prices = {a["code"]: float(a.get("price", 0)) for a in werk["articles"]}
    workers, hold = sim_params(werk["settings"]["calc"])
    return orders, stock, prices, workers, hold
