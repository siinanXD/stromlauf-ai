"""Stammdaten fuer die Vorkalkulation aus JSON (Testwerk-Datei, plant_settings) in Rechenkern-Objekte."""

from app.werk import calc

HOURLY_LABEL = "Maschinenstundensatz"


def hourly_rate(specs: list[dict]) -> float | None:
    """Maschinenstundensatz (EUR/h) aus den Kennzahlen einer Maschine; None, wenn fehlt oder kein Zahlwert."""
    for spec in specs:
        if spec.get("label") == HOURLY_LABEL:
            return calc.parse_number(spec.get("value", ""))
    return None


def settings_from_json(value: dict) -> calc.Settings:
    calendars = value["calendars"]
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
