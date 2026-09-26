"""Kalenderwoche 40 des Testwerks laeuft vollstaendig durch die Simulation (ohne Datenbank)."""

import json
from pathlib import Path

from app.werk.masterdata import inputs_from_werk, sim_inputs_from_werk
from app.werk.sim import simulate

DATA = Path(__file__).resolve().parents[2] / "examples" / "testwerk" / "testwerk.json"


def test_week_40_runs_to_completion():
    werk = json.loads(DATA.read_text(encoding="utf-8"))
    articles, materials, settings = inputs_from_werk(werk)
    orders, stock, prices, workers, hold = sim_inputs_from_werk(werk, articles)
    result = simulate(orders, stock, materials, settings, workers, hold, prices)
    assert len(result["orders"]) == 14
    assert all(o["shipped_at"] for o in result["orders"])
    assert any(s["stage"] == "credit" for o in result["orders"] for s in o["stages"])
    assert any(p["from_stock"] > 0 for o in result["orders"] for p in o["positions"])
    assert any(s["stage"] == "office:gf" for o in result["orders"] for s in o["stages"])
    assert 0 <= result["kpis"]["on_time_rate"] <= 1
    assert not result["warnings"]
