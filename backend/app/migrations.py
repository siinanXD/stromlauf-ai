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
]


def upgrade_statements() -> list[str]:
    return [
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"
        for table, column, ddl in ADDITIVE_COLUMNS
    ]
