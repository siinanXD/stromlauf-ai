from datetime import date, datetime

from app.werk.calc import PAPER, Article, BomLine, Maker, Material, OfficeStep, Settings, Step
from app.werk.sim import Customer, SimLine, SimOrder, simulate

OFFICE = {"days": [0, 1, 2, 3, 4], "from": "07:00", "to": "16:00"}
SHIPPING = {"days": [0, 1, 2, 3, 4], "from": "06:00", "to": "22:00"}
MONDAY = datetime(2026, 9, 28, 7, 0)

SETTINGS = Settings(
    office=OFFICE, production="24/7", shipping=SHIPPING,
    office_steps=[
        OfficeStep("ks", "Kundenservice", 30), OfficeStep("fin", "Finanzen", 60),
        OfficeStep("av", "Arbeitsvorbereitung", 45), OfficeStep("gf", "Geschäftsführung", 30, 100),
    ],
    office_rate=60, truck_capacity=33, load_min=45, docks=8, dock_rate=40,
)
WORKERS = {"ks": 2, "fin": 1, "av": 1, "gf": 1}
MATERIALS = {PAPER: Material(PAPER, "Rohpapier", "t", None, "", Maker("pm1", "PM1", 3.6, 1500), [])}
RICH = Customer("c1", "Muster Handel", 1_000_000)


def article(code="TP", line="L1", rate=35, upp=84, routing=None) -> Article:
    return Article(
        code, code, code, "Paket", upp, 1200, 98, 125, 3, 16, 3, line,
        routing if routing is not None else [Step(f"{line}-UR", f"{line}-UR", line, rate, "unit_min", 20, True, 250, "")],
        [BomLine("PALETTE", 1, "pallet")],
    )


def order(number, lines, received=MONDAY, due=None, customer=RICH) -> SimOrder:
    return SimOrder(number, number, customer, received, due, lines)


def run(orders, stock=None, prices=None, credit_hold=540):
    return simulate(orders, stock or {}, MATERIALS, SETTINGS, WORKERS, credit_hold, prices or {"TP": 2.0, "KR": 2.0})


def stage(result, number, key):
    o = next(o for o in result["orders"] if o["number"] == number)
    return next((s for s in o["stages"] if s["stage"] == key), None)


def test_second_order_waits_for_the_only_finance_person():
    result = run([order("A1", [SimLine(article(), 84)]), order("A2", [SimLine(article(), 84)])])
    ks1, ks2 = stage(result, "A1", "office:ks"), stage(result, "A2", "office:ks")
    assert ks1["start"] == ks2["start"]  # zwei Personen im Kundenservice
    fin1, fin2 = stage(result, "A1", "office:fin"), stage(result, "A2", "office:fin")
    assert fin2["arrive"] < fin2["start"] == fin1["end"]


def test_credit_limit_exceeded_adds_one_working_day_of_clarification():
    poor = Customer("c2", "Klinik West", 100)
    result = run([order("A1", [SimLine(article(), 840)], customer=poor)])
    credit = stage(result, "A1", "credit")
    assert credit is not None and credit["resource"] == "Finanzen (Klärung)"
    assert credit["end"] == "2026-09-29T08:30"  # Finanzen fertig Mo 08:30, + 9 h Bürozeit
    assert stage(run([order("A1", [SimLine(article(), 840)])]), "A1", "credit") is None


def test_management_release_only_from_100_pallets():
    small = run([order("A1", [SimLine(article(), 10, "pallet")])])
    large = run([order("A1", [SimLine(article(), 100, "pallet")])])
    assert stage(small, "A1", "office:gf") is None
    assert stage(large, "A1", "office:gf") is not None


def test_stock_covers_order_without_production():
    result = run([order("A1", [SimLine(article(), 840)])], stock={"TP": 1000})
    o = result["orders"][0]
    assert o["positions"][0] == {"code": "TP", "units": 840, "from_stock": 840, "produced": 0}
    assert not any(s["stage"].startswith(("paper", "line")) for s in o["stages"])
    assert o["shipped_at"] is not None


def test_partial_stock_is_reserved_once_and_never_negative():
    result = run(
        [order("A1", [SimLine(article(), 250)]), order("A2", [SimLine(article(), 250)])], stock={"TP": 300}
    )
    first, second = result["orders"]
    assert first["positions"][0]["from_stock"] == 250
    assert second["positions"][0]["from_stock"] == 50 and second["positions"][0]["produced"] == 200
    assert all(units >= 0 for _, units in result["stock"]["TP"]["points"])


def test_line_serves_the_earliest_due_date_first():
    long_job = order("A1", [SimLine(article(), 20_000)])
    later = order("A2", [SimLine(article(), 840)], received=datetime(2026, 9, 28, 7, 5), due=date(2026, 10, 9))
    sooner = order("A3", [SimLine(article(), 840)], received=datetime(2026, 9, 28, 7, 10), due=date(2026, 10, 1))
    result = run([long_job, later, sooner])
    assert stage(result, "A3", "line:0:0")["start"] < stage(result, "A2", "line:0:0")["start"]


def test_trucks_wait_when_all_docks_are_busy():
    result = run([order("A1", [SimLine(article(), 300, "pallet")])], stock={"TP": 300 * 84})
    trucks = result["orders"][0]["trucks"]
    assert len(trucks) == 10
    assert sorted({t["dock"] for t in trucks}) == list(range(1, 9))
    ninth = sorted(trucks, key=lambda t: t["start"])[8]
    assert ninth["start"] >= min(t["end"] for t in trucks)
    for dock in range(1, 9):
        spans = sorted((t["start"], t["end"]) for t in trucks if t["dock"] == dock)
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:], strict=False))


def test_stock_rises_at_line_end_and_falls_when_loaded():
    result = run([order("A1", [SimLine(article(), 84)])], stock={"TP": 0})
    points = result["stock"]["TP"]["points"]
    assert [units for _, units in points] == [0, 84, 0]
    line_end = stage(result, "A1", "line:0:0")["end"]
    assert points[1][0] == line_end


def test_kpis_on_time_rate_and_utilization():
    result = run([
        order("A1", [SimLine(article(), 840)], due=date(2026, 10, 30)),
        order("A2", [SimLine(article(), 840)], due=date(2026, 9, 27)),
    ])
    kpis = result["kpis"]
    assert kpis["on_time_rate"] == 0.5
    assert 0 < kpis["utilization"]["line:L1"] <= 1
    assert kpis["avg_wait_hours"]["office:fin"] > 0


def test_empty_order_list():
    result = run([])
    assert result["orders"] == [] and result["kpis"]["on_time_rate"] is None


def test_article_without_routing_warns_and_still_ships():
    result = run([order("A1", [SimLine(article(routing=[]), 84)])])
    assert any("Arbeitsplan" in w for w in result["warnings"])
    assert result["orders"][0]["shipped_at"] is not None


def test_same_input_same_result():
    orders = [order("A1", [SimLine(article(), 840)]), order("A2", [SimLine(article("KR", "L2"), 480)])]
    assert run(orders) == run(orders)
