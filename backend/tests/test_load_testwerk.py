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


def test_master_data_payload_resolves_machine_keys_and_flattens_tech():
    werk = {
        "materials": [{"code": "ROHPAPIER", "name": "Rohpapier", "unit": "t", "price": None, "price_source": "",
                       "made_on": {"machine": "pm1-s6", "rate_per_h": 3.6, "basis": "b"}, "bom": []}],
        "articles": [{"code": "TP", "name": "TP", "unit_name": "Paket", "units_per_pallet": 84,
                      "tech": {"sheets_per_unit": 1200, "sheet_w_mm": 98, "sheet_l_mm": 125, "plies": 3,
                               "gsm": 16, "waste_pct": 3},
                      "line": "L1", "description": "",
                      "routing": [{"machine": "l1-ur", "rate": 35, "rate_unit": "unit_min", "setup_min": 20,
                                   "coupled": True, "basis": "x"}],
                      "bom": [{"material": "ROHPAPIER", "qty": 1, "per": "unit"}]}],
        "settings": {"calc": {"docks": 8}},
    }
    payload = loader.master_data_payload(werk, {"pm1-s6": "id-pm", "l1-ur": "id-ur"})
    assert payload["materials"][0]["made_on_machine_id"] == "id-pm"
    assert payload["materials"][0]["made_rate_per_h"] == 3.6
    article = payload["articles"][0]
    assert article["sheets_per_unit"] == 1200 and "tech" not in article
    assert article["routing"][0]["machine_id"] == "id-ur" and "machine" not in article["routing"][0]
    assert payload["settings"] == {"calc": {"docks": 8}}
