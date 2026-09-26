"""Beispielauftrag gegen die echten Testwerk-Stammdaten (ohne Datenbank)."""

import json
from datetime import date, datetime
from pathlib import Path

from app.werk.calc import Position, calculate
from app.werk.masterdata import inputs_from_werk

DATA = Path(__file__).resolve().parents[2] / "examples" / "testwerk" / "testwerk.json"


def test_example_order_from_the_mockup():
    articles, materials, settings = inputs_from_werk(json.loads(DATA.read_text(encoding="utf-8")))
    positions = [
        Position(articles["TP-3L-8x150"], 10_000, "unit"),
        Position(articles["KR-2L-4x64"], 40, "pallet"),
    ]
    result = calculate(datetime(2026, 9, 25, 15, 30), date(2026, 10, 2), positions, materials, settings)
    assert result["ready_at"].startswith("2026-09-28T17:")
    assert result["summary"]["pallets"] == 160
    assert result["summary"]["trucks"] == 5
    assert result["summary"]["bottleneck"] == "L1-UR Umroller Toilettenpapier"
    assert result["meets_due"] is True
    assert not result["warnings"]
    assert result["costs"]["total"]["total"] > 0
