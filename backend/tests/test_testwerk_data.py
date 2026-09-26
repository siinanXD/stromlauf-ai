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
