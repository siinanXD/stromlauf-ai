"""Modell und Migrationen bleiben deckungsgleich: jede Tabelle und jeder Index kommt aus einer Revision."""

import re
from pathlib import Path

from app import models  # noqa: F401
from app.db import Base

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
BASELINE = VERSIONS / "0001_stromlauf_baseline.py"


def _all_sources() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(VERSIONS.glob("*.py")))


def test_jede_modelltabelle_kommt_aus_einer_migration():
    created = set(re.findall(r"op\.create_table\(\s*['\"]([a-z_0-9]+)['\"]", _all_sources()))
    expected = {table.name for table in Base.metadata.sorted_tables}
    assert expected <= created, sorted(expected - created)


def test_jeder_modellindex_kommt_aus_einer_migration():
    source = _all_sources()
    created = set(re.findall(r"op\.create_index\((?:op\.f\()?['\"]([a-z_0-9]+)['\"]", source))
    # Schleifen-Indizes wie op.f(f"ix_{table}_workspace_id") ueber SCOPED_TABLES
    looped = {f"ix_{t}_workspace_id" for t in re.findall(r'^    "([a-z_]+)",$', source, re.M)}
    expected = {index.name for table in Base.metadata.sorted_tables for index in table.indexes}
    assert expected <= created | looped, sorted(expected - created - looped)


def test_baseline_tables_liste_deckt_die_baseline_ab():
    source = BASELINE.read_text(encoding="utf-8")
    match = re.search(r"^TABLES = (\[.*?\])$", source, re.M)
    assert match, "TABLES-Liste fehlt"
    namespace: dict = {}
    exec(f"TABLES = {match.group(1)}", namespace)  # noqa: S102 (Testdatei, eigener Quelltext)
    created = re.findall(r"op\.create_table\('([a-z_0-9]+)'", source)
    assert namespace["TABLES"] == created  # gleiche Tabellen, gleiche Reihenfolge wie im upgrade()
    assert set(created) <= {table.name for table in Base.metadata.sorted_tables}
