"""Additive Schema-Aenderungen an bestehenden Tabellen.

`create_all` legt nur fehlende Tabellen an, keine neuen Spalten. Neue Spalten auf bestehenden
Tabellen stehen deshalb hier und werden beim Start idempotent angelegt. Nicht-additive Aenderungen
(Umbenennen, Typwechsel, Loeschen) brauchen ein richtiges Migrationswerkzeug (Alembic).
"""

# (Tabelle, Spalte, Typ inkl. Standardwert) - Standardwert muss zum Modell passen
ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    ("halls", "kind", "VARCHAR(24) NOT NULL DEFAULT 'generic'"),
    ("halls", "site_x", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    ("halls", "site_y", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    ("halls", "site_w", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    ("halls", "site_h", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    ("machines", "line", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("articles", "price", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    # Volltext fuer die Hybrid-Suche; generierte Spalte, Postgres fuellt sie fuer alte Zeilen selbst
    ("chunks", "tsv", "tsvector GENERATED ALWAYS AS (to_tsvector('german', content)) STORED"),
]

# Indizes auf Spalten, die erst per ADDITIVE_COLUMNS entstehen (create_all legt sie nur auf neuen Tabellen an)
ADDITIVE_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON chunks USING gin (tsv)",
]


def upgrade_statements() -> list[str]:
    columns = [
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"
        for table, column, ddl in ADDITIVE_COLUMNS
    ]
    return columns + ADDITIVE_INDEXES
