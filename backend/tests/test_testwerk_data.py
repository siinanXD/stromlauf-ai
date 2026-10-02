"""Beispieldaten Testwerk Tissue: vollstaendig, in sich stimmig, jede Kennzahl mit Quelle."""

import json
from pathlib import Path

import pytest

from app.models import MachineType

DATA = Path(__file__).resolve().parents[2] / "examples" / "testwerk" / "testwerk.json"


@pytest.fixture(scope="module")
def werk() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _hall(werk: dict, name: str) -> dict:
    return next(h for h in werk["halls"] if h["name"] == name)


def test_four_halls_with_unique_names(werk):
    names = [h["name"] for h in werk["halls"]]
    assert names == ["Papiermaschine PM1", "Verarbeitung", "Lager & Versand", "Büro"]


def test_production_has_six_lines_of_main_packaging_palletizer(werk):
    hall = _hall(werk, "Verarbeitung")
    lines = list(dict.fromkeys(m["line"] for m in hall["machines"]))
    assert len(lines) == 6
    for line in lines:
        types = [m["machine_type"] for m in hall["machines"] if m["line"] == line]
        assert types == ["main", "packaging", "robot"], line


def test_names_unique_and_types_valid(werk):
    machines = [m for h in werk["halls"] for m in h["machines"]]
    assert len(machines) == 30
    assert len({m["name"] for m in machines}) == len(machines)
    assert all(m["machine_type"] in set(MachineType) for m in machines)


def test_every_machine_has_specs_with_source(werk):
    for machine in (m for h in werk["halls"] for m in h["machines"]):
        assert machine["specs"], machine["name"]
        for spec in machine["specs"]:
            assert spec["label"] and spec["value"] and spec["source"], (machine["name"], spec)


def test_warehouse_has_eight_gates(werk):
    """Die Tore sind eine gewoehnliche Kennzahl mit Quelle, keine Eigenschaft der Halle."""
    specs = [s for m in _hall(werk, "Lager & Versand")["machines"] for s in m["specs"]]
    assert sum(int(s["value"]) for s in specs if s["label"] == "Anzahl Tore") == 8
