from datetime import date, datetime

import pytest

from app.werk.calc import (
    PAPER,
    Article,
    BomLine,
    Maker,
    Material,
    OfficeStep,
    Position,
    Settings,
    Step,
    calculate,
    paper_kg_per_unit,
    parse_number,
)

OFFICE = {"days": [0, 1, 2, 3, 4], "from": "07:00", "to": "16:00"}
SHIPPING = {"days": [0, 1, 2, 3, 4], "from": "06:00", "to": "22:00"}
FRIDAY = datetime(2026, 9, 25, 15, 30)


def step(name, line, rate, unit="unit_min", setup=0, coupled=True, hourly=100.0):
    return Step(name, name, line, rate, unit, setup, coupled, hourly, "")


def tp(routing=None) -> Article:
    return Article(
        id="tp", code="TP", name="Toilettenpapier", unit_name="Paket", units_per_pallet=84,
        sheets_per_unit=1200, sheet_w_mm=98, sheet_l_mm=125, plies=3, gsm=16, waste_pct=3,
        line="L1",
        routing=routing if routing is not None else [
            step("L1-UR", "L1", 35, setup=20, hourly=250),
            step("L1-VP", "L1", 220, setup=15, hourly=120),
            step("L1-PAL", "L1", 60, setup=10, hourly=60),
        ],
        bom=[BomLine("HUELSE", 8, "unit"), BomLine("PALETTE", 1, "pallet")],
    )


def kr(line="L2") -> Article:
    return Article(
        id="kr", code="KR", name="Kuechenrolle", unit_name="Paket", units_per_pallet=48,
        sheets_per_unit=256, sheet_w_mm=225, sheet_l_mm=250, plies=2, gsm=20, waste_pct=3,
        line=line,
        routing=[step(f"{line}-UR", line, 31, setup=15, hourly=250)],
        bom=[BomLine("HUELSE", 4, "unit"), BomLine("PALETTE", 1, "pallet")],
    )


MATERIALS = {
    PAPER: Material(PAPER, "Rohpapier", "t", 0, "", Maker("pm1", "PM1-S6 Aufrollung", 3.6, 1500),
                    [BomLine("ZELLSTOFF", 0.55)]),
    "ZELLSTOFF": Material("ZELLSTOFF", "Zellstoff", "t", 1000, "Richtwert (Annahme)"),
    "HUELSE": Material("HUELSE", "Huelse", "Stk", 0.02, "Richtwert (Annahme)"),
    "PALETTE": Material("PALETTE", "Palette", "Stk", 10, "Richtwert (Annahme)"),
}

SETTINGS = Settings(
    office=OFFICE, production="24/7", shipping=SHIPPING,
    office_steps=[
        OfficeStep("ks", "Kundenservice", 30), OfficeStep("fin", "Finanzen", 60),
        OfficeStep("av", "Arbeitsvorbereitung", 45), OfficeStep("gf", "Geschaeftsfuehrung", 30, 100),
    ],
    office_rate=60, truck_capacity=33, load_min=45, docks=8, dock_rate=40,
)


def run(positions, due=None, received=FRIDAY, materials=MATERIALS):
    return calculate(received, due, positions, materials, SETTINGS)


def station(result, key):
    return next(s for s in result["stations"] if s["key"] == key)


def test_paper_per_unit_from_sheets_area_plies_and_waste():
    assert paper_kg_per_unit(tp()) == pytest.approx(0.7268, abs=1e-4)


@pytest.mark.parametrize(
    ("text", "value"),
    [("1.500", 1500), ("2,8", 2.8), ("~30.000", 30000), ("250", 250), ("30–90", None), ("Dampf", None), ("", None)],
)
def test_parse_number_reads_german_numbers(text, value):
    assert parse_number(text) == value


def test_material_explosion_over_two_levels():
    result = run([Position(tp(), 10_000)])
    need = {m["code"]: m["qty"] for m in result["materials"]}
    assert need[PAPER] == pytest.approx(7.268, abs=1e-3)
    assert need["ZELLSTOFF"] == pytest.approx(7.268 * 0.55, abs=1e-3)
    assert need["HUELSE"] == 80_000
    assert need["PALETTE"] == 120
    zellstoff = next(m for m in result["materials"] if m["code"] == "ZELLSTOFF")
    assert zellstoff["level"] == 1 and zellstoff["parent"] == PAPER


def test_recipe_basis_is_given_once_for_the_whole_order():
    result = run([Position(tp(), 10_000), Position(kr(), 1920)])
    zellstoff = next(m for m in result["materials"] if m["code"] == "ZELLSTOFF")
    assert zellstoff["basis"] == "0,55 je t Rohpapier × 8,41 t"


def test_friday_order_waits_for_monday_office_and_line_uses_bottleneck():
    result = run([Position(tp(), 10_000)])
    assert station(result, "office:ks")["end"] == "2026-09-25T16:00"
    assert station(result, "office:fin")["start"] == "2026-09-28T07:00"
    assert station(result, "office:gf")["end"] == "2026-09-28T09:15"  # 120 Paletten: GF gibt frei
    line = station(result, "line:0:0")
    assert line["bottleneck"] == "L1-UR"
    assert line["work_minutes"] == pytest.approx(20 + 10_000 / 35)
    assert result["summary"]["pallets"] == 120
    assert result["summary"]["trucks"] == 4
    assert station(result, "ship")["work_minutes"] == 45


def test_small_order_skips_management_release():
    result = run([Position(tp(), 10, "pallet")])
    assert not any(s["key"] == "office:gf" for s in result["stations"])


def test_pallet_rate_is_converted_to_units_per_minute():
    article = tp([step("L1-UR", "L1", 35), step("LV-SW", "L1", 21, unit="pallet_h")])
    line = station(run([Position(article, 840)]), "line:0:0")
    assert line["bottleneck"] == "LV-SW"  # 21 Paletten/h × 84 ÷ 60 = 29,4 Pakete/min
    assert line["work_minutes"] == pytest.approx(840 / 29.4)


def test_positions_on_the_same_line_run_one_after_another():
    result = run([Position(kr("L2"), 480), Position(kr("L2"), 480)])
    first, second = station(result, "line:0:0"), station(result, "line:1:0")
    assert second["start"] >= first["end"]


def test_positions_on_different_lines_run_in_parallel():
    result = run([Position(tp(), 10_000), Position(kr("L2"), 1920)])
    assert station(result, "line:1:0")["start"] < station(result, "line:0:0")["end"]


def test_example_order_ready_monday_evening_and_due_date_holds():
    result = run([Position(tp(), 10_000), Position(kr(), 40, "pallet")], due=date(2026, 10, 2))
    assert result["ready_at"].startswith("2026-09-28T17:0")
    assert result["summary"]["pallets"] == 160
    assert result["summary"]["trucks"] == 5
    assert result["meets_due"] is True
    assert result["days_delta"] == 4


def test_missed_due_date_reports_days_late():
    result = run([Position(tp(), 10_000)], due=date(2026, 9, 25))
    assert result["meets_due"] is False
    assert result["days_delta"] == -3


def test_costs_per_position_and_shared_costs_by_pallets():
    result = run([Position(tp(), 8400)])
    cost = result["costs"]["positions"][0]
    line_minutes = 20 + 8400 / 35
    assert cost["production"] == pytest.approx(line_minutes / 60 * (250 + 120 + 60) + (8400 * 0.72682 / 1000) / 3.6 * 1500, rel=1e-3)
    assert cost["material"] == pytest.approx(8400 * 8 * 0.02 + 100 * 10 + 8400 * 0.72682 / 1000 * 0.55 * 1000, rel=1e-3)
    office_minutes = 30 + 60 + 45 + 30
    assert cost["office"] == pytest.approx(office_minutes / 60 * 60)
    assert cost["shipping"] == pytest.approx(4 * 45 / 60 * 40)  # 100 Paletten -> 4 LKW
    assert cost["per_unit"] == pytest.approx(cost["total"] / 8400)


def test_missing_hourly_rate_costs_nothing_and_warns():
    article = tp([step("L1-UR", "L1", 35, hourly=None)])
    result = run([Position(article, 840)])
    assert any("L1-UR" in w for w in result["warnings"])


def test_article_without_routing_warns_instead_of_failing():
    result = run([Position(tp(routing=[]), 840)])
    assert any("Arbeitsplan" in w for w in result["warnings"])
    assert result["ready_at"]


def test_quantity_must_be_positive():
    with pytest.raises(ValueError):
        run([Position(tp(), 0)])
