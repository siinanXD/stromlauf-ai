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


# --- Testdokumentation (--docs) ---------------------------------------------------------------


def test_doc_type_from_filename():
    assert loader.doc_type_of("03_Klemmenplan_UR-01.csv") == "terminal_plan"
    assert loader.doc_type_of("06_Betriebsanleitung_PM1-AR.md") == "manual"
    assert loader.doc_type_of("README.md") is None


def test_machine_for_needs_a_unique_prefix():
    machines = [{"id": "1", "name": "L1-UR Umroller"}, {"id": "2", "name": "L1-VP Verpacker"},
                {"id": "3", "name": "L1-PAL Palettierer"}, {"id": "4", "name": "L2-PAL Palettierer"}]
    assert loader.machine_for(machines, "l1-ur")["id"] == "1"
    assert loader.machine_for(machines, "L1-") is None
    assert loader.machine_for(machines, "PM1-S6") is None


def test_new_faults_skips_known_symptoms():
    existing = [{"symptom": "Band steht"}]
    proposed = [{"symptom": "band steht "}, {"symptom": "-H2 leuchtet"}]
    assert loader.new_faults(existing, proposed) == [{"symptom": "-H2 leuchtet"}]


def test_stale_faults_are_the_ones_imported_from_the_manual():
    faults = [{"id": "1", "doc_ref": "Betriebsanleitung Kap. 7"}, {"id": "2", "doc_ref": "Stromlaufplan Blatt 4"}, {"id": "3", "doc_ref": ""}]
    assert [f["id"] for f in loader.stale_faults(faults)] == ["1"]
