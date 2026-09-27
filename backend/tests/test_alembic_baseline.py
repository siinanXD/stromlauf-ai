"""Die Baseline-Migration muss alle Tabellen des Modells anlegen (kein Drift zwischen Modell und Migration)."""

import re
from pathlib import Path

from app import models  # noqa: F401
from app.db import Base

BASELINE = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_stromlauf_baseline.py"


def test_baseline_legt_jede_modelltabelle_an():
    source = BASELINE.read_text(encoding="utf-8")
    created = set(re.findall(r"op\.create_table\('([a-z_]+)'", source))
    expected = {table.name for table in Base.metadata.sorted_tables}
    assert created == expected


def test_baseline_legt_jeden_modellindex_an():
    source = BASELINE.read_text(encoding="utf-8")
    created = set(re.findall(r"op\.create_index\('([a-z_]+)'", source))
    expected = {index.name for table in Base.metadata.sorted_tables for index in table.indexes}
    assert created == expected


def test_baseline_tables_liste_stimmt_mit_reihenfolge_ueberein():
    namespace: dict = {}
    source = BASELINE.read_text(encoding="utf-8")
    match = re.search(r"^TABLES = (\[.*?\])$", source, re.M)
    assert match, "TABLES-Liste fehlt"
    exec(f"TABLES = {match.group(1)}", namespace)  # noqa: S102 (Testdatei, eigener Quelltext)
    assert namespace["TABLES"] == [table.name for table in Base.metadata.sorted_tables]
