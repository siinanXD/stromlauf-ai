import pytest

from app.migrations import upgrade_statements
from app.werk.site import (
    MAX_DOCKS,
    check_site_flows,
    clean_specs,
    dock_count,
    key_figure,
    place_halls,
)


def test_upgrade_statements_add_each_column_idempotently():
    statements = upgrade_statements()
    assert statements[0] == (
        "ALTER TABLE halls ADD COLUMN IF NOT EXISTS kind VARCHAR(24) NOT NULL DEFAULT 'generic'"
    )
    columns = [(s.split()[2], s.split()[8]) for s in statements]
    assert columns == [
        ("halls", "kind"),
        ("halls", "site_x"),
        ("halls", "site_y"),
        ("halls", "site_w"),
        ("halls", "site_h"),
        ("machines", "line"),
    ]


def test_place_halls_puts_unplaced_halls_in_rows_of_three():
    assert place_halls([(0, 0, 0, 0)] * 4) == [
        (40, 40, 360, 260),
        (460, 40, 360, 260),
        (880, 40, 360, 260),
        (40, 360, 360, 260),
    ]


def test_place_halls_keeps_placed_halls_and_starts_below_them():
    placed = (100, 100, 300, 200)
    assert place_halls([placed, (0, 0, 0, 0)]) == [placed, (40, 360, 360, 260)]


@pytest.mark.parametrize(
    "flows",
    [[("a", "a")], [("a", "x")], [("a", "b"), ("a", "b")]],
    ids=["self-loop", "unknown-hall", "duplicate"],
)
def test_check_site_flows_rejects_invalid_flows(flows):
    with pytest.raises(ValueError):
        check_site_flows(flows, {"a", "b"})


def test_check_site_flows_accepts_valid_flows():
    check_site_flows([("a", "b"), ("b", "a")], {"a", "b"})


def test_clean_specs_trims_and_drops_rows_without_label():
    specs = [
        {"label": " Leistung ", "value": " 10 ", "unit": "Logs/min", "source": " x "},
        {"label": "  ", "value": "1"},
    ]
    assert clean_specs(specs) == [
        {"label": "Leistung", "value": "10", "unit": "Logs/min", "source": "x", "position": 0}
    ]


def test_key_figure_is_first_value_with_unit():
    assert key_figure([{"value": "2.200", "unit": "m/min"}, {"value": "5", "unit": "m"}]) == "2.200 m/min"
    assert key_figure([{"value": "Dampf", "unit": ""}]) == "Dampf"
    assert key_figure([]) == ""


def test_dock_count_sums_numeric_gate_specs():
    specs = [
        {"label": "Anzahl Tore", "value": "8"},
        {"label": "Anzahl Tore", "value": "zwei"},
        {"label": "Leistung", "value": "4"},
    ]
    assert dock_count(specs) == 8


def test_dock_count_ignores_non_decimal_digits():
    assert dock_count([{"label": "Anzahl Tore", "value": "²"}]) == 0


def test_dock_count_is_capped():
    assert dock_count([{"label": "Anzahl Tore", "value": "88888888"}]) == MAX_DOCKS
