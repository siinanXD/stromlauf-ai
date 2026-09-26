"""Beispieldaten Testwerk Tissue: vollstaendig, in sich stimmig, jede Kennzahl mit Quelle."""

import json
from pathlib import Path

import pytest

from app.models import MachineType
from app.werk.site import HALL_KINDS, dock_count

DATA = Path(__file__).resolve().parents[2] / "examples" / "testwerk" / "testwerk.json"


@pytest.fixture(scope="module")
def werk() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _hall(werk: dict, kind: str) -> dict:
    return next(h for h in werk["halls"] if h["kind"] == kind)


def test_one_hall_per_kind(werk):
    kinds = [h["kind"] for h in werk["halls"]]
    assert sorted(kinds) == sorted(["base", "production", "warehouse", "office"])
    assert all(kind in HALL_KINDS for kind in kinds)


def test_production_has_six_lines_of_main_packaging_palletizer(werk):
    hall = _hall(werk, "production")
    by_key = {m["key"]: m for m in hall["machines"]}
    lines = list(dict.fromkeys(m["line"] for m in hall["machines"]))
    assert len(lines) == 6
    for line in lines:
        members = {m["key"] for m in hall["machines"] if m["line"] == line}
        assert len(members) == 3, line
        chain = [(a, b) for a, b, _ in hall["flows"] if a in members and b in members]
        types = {(by_key[a]["machine_type"], by_key[b]["machine_type"]) for a, b in chain}
        assert types == {("main", "packaging"), ("packaging", "robot")}, line


def test_flows_reference_machines_of_the_same_hall(werk):
    for hall in werk["halls"]:
        keys = {m["key"] for m in hall["machines"]}
        for source, target, _label in hall["flows"]:
            assert source in keys and target in keys, (hall["name"], source, target)


def test_keys_unique_and_types_valid(werk):
    machines = [m for h in werk["halls"] for m in h["machines"]]
    assert len(machines) == 30
    assert len({m["key"] for m in machines}) == len(machines)
    assert len({m["name"] for m in machines}) == len(machines)
    assert all(m["machine_type"] in set(MachineType) for m in machines)


def test_every_machine_has_specs_with_source(werk):
    for machine in (m for h in werk["halls"] for m in h["machines"]):
        assert machine["specs"], machine["name"]
        for spec in machine["specs"]:
            assert spec["label"] and spec["value"] and spec["source"], (machine["name"], spec)


def test_site_flows_and_rects(werk):
    names = {h["name"] for h in werk["halls"]}
    assert all(a in names and b in names for a, b, _ in werk["site_flows"])
    assert all(h["site"]["w"] > 0 and h["site"]["h"] > 0 for h in werk["halls"])


def test_warehouse_has_eight_gates(werk):
    specs = [s for m in _hall(werk, "warehouse")["machines"] for s in m["specs"]]
    assert dock_count(specs) == 8


# --- Stammdaten fuer die Vorkalkulation (Teil 2) ----------------------------------------------


def _machines_by_key(werk: dict) -> dict:
    return {m["key"]: m for h in werk["halls"] for m in h["machines"]}


def test_eight_articles_cover_all_six_lines(werk):
    lines = {m["line"] for m in _hall(werk, "production")["machines"]}
    assert len(werk["articles"]) == 8
    assert len({a["code"] for a in werk["articles"]}) == 8
    assert {a["line"] for a in werk["articles"]} == lines


def test_routing_and_bom_reference_existing_machines_and_materials(werk):
    machines = _machines_by_key(werk)
    codes = {m["code"] for m in werk["materials"]}
    for article in werk["articles"]:
        assert article["routing"], article["code"]
        for step in article["routing"]:
            assert step["machine"] in machines, (article["code"], step["machine"])
            assert machines[step["machine"]]["line"] == article["line"]
            assert step["rate"] > 0 and step["rate_unit"] in {"unit_min", "pallet_h"} and step["basis"]
        for line in article["bom"]:
            assert line["material"] in codes and line["per"] in {"unit", "pallet"}
    for material in werk["materials"]:
        for line in material["bom"]:
            assert line["material"] in codes


def test_purchased_materials_have_price_and_paper_is_made_on_pm1(werk):
    for material in werk["materials"]:
        if material.get("made_on"):
            continue
        assert material["price"] > 0 and material["price_source"], material["code"]
    paper = next(m for m in werk["materials"] if m["code"] == "ROHPAPIER")
    assert paper["made_on"]["machine"] == "pm1-s6" and paper["made_on"]["rate_per_h"] > 0


def test_machines_used_for_production_have_an_hourly_rate(werk):
    machines = _machines_by_key(werk)
    used = {s["machine"] for a in werk["articles"] for s in a["routing"]} | {"pm1-s6"}
    for key in used:
        labels = [s["label"] for s in machines[key]["specs"]]
        assert "Maschinenstundensatz" in labels, key
        assert labels[0] != "Maschinenstundensatz", key  # Kachel zeigt weiter die Leistung


def test_settings_for_calculation(werk):
    settings = werk["settings"]["calc"]
    assert settings["truck_capacity"] == 33 and settings["docks"] == 8
    assert [s["key"] for s in settings["office_steps"]] == ["ks", "fin", "av", "gf"]


# --- Leitstand (Teil 3) ------------------------------------------------------------------------


def test_orders_customers_stock_and_prices(werk):
    names = {c["name"] for c in werk["customers"]}
    codes = {a["code"] for a in werk["articles"]}
    assert len(names) == 6 and all(c["credit_limit"] > 0 for c in werk["customers"])
    assert len(werk["orders"]) == 14 and len({o["number"] for o in werk["orders"]}) == 14
    for order in werk["orders"]:
        assert order["customer"] in names
        assert "2026-09-28" <= order["received_at"][:10] <= "2026-10-02"
        assert order["lines"] and all(line["article"] in codes and line["quantity"] > 0 for line in order["lines"])
    assert len(werk["stock"]) == 5 and all(s["article"] in codes and s["units"] > 0 for s in werk["stock"])
    assert all(a["price"] > 0 for a in werk["articles"])
    calc = werk["settings"]["calc"]
    assert all(step["workers"] >= 1 for step in calc["office_steps"]) and calc["credit_hold_min"] > 0
