"""Aufteilung der Index-Zeilen fuer das Modell (app/api/machine_map.py::split_rows), Issue #39."""

from app.api.machine_map import split_rows


def test_split_rows_trennt_stuecklistenzeilen_von_planfundstellen():
    rows = [
        ("-K1", "| -K1 | Schuetz | +ST1 |", "bom", None, ""),
        ("9K1", "9K1 A1 A2", "schematic", 9, "V1 Gate Control Circuit"),
        ("9K1", "6 ... 9K1 Contactor", "schematic", 41, "Nomenclature"),
        ("4Q1", "4Q1 80A", "schematic", 4, "Mains Power Supply"),
        ("-M1", "-M1 U1 V1 W1", "schematic", None, ""),
    ]
    bom_rows, index_hits, known = split_rows(rows)
    assert bom_rows == [("-K1", "| -K1 | Schuetz | +ST1 |"), ("9K1", "6 ... 9K1 Contactor")]
    assert index_hits == [("4Q1", 4, "Mains Power Supply"), ("9K1", 9, "V1 Gate Control Circuit"), ("-M1", None, "")]
    assert known == {"-K1", "9K1", "4Q1", "-M1"}
