"""Lader Testwerk: ersetzt nur Hallen, die er selbst angelegt hat."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "load_testwerk.py"
_spec = importlib.util.spec_from_file_location("load_testwerk", SCRIPT)
loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loader)

WERK = {"name": "Testwerk Tissue", "halls": [{"name": "Verarbeitung", "description": "6 Linien"}]}


def test_description_carries_the_marker():
    assert loader.marked_description(WERK, WERK["halls"][0]) == "Testwerk Tissue: 6 Linien"


def test_split_existing_separates_own_from_foreign_halls():
    own = {"id": "1", "name": "Verarbeitung", "description": "Testwerk Tissue: 6 Linien"}
    foreign = {"id": "2", "name": "Verarbeitung", "description": "meine eigene Halle"}
    other = {"id": "3", "name": "Andere Halle", "description": "Testwerk Tissue: x"}
    assert loader.split_existing([own, foreign, other], WERK) == ([own], [foreign])
