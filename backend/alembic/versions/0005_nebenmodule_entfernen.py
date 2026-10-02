"""Nebenmodule entfernen: Tabellen der gestrichenen Module fallen weg (Issue #123).

Die Baseline 0001 legt diese Tabellen nicht mehr an. Diese Revision raeumt sie auf Datenbanken ab, die vor dem
Rueckbau entstanden sind; auf einer frischen Datenbank ist jedes Statement ein No-op (IF EXISTS). Abhaengige
Tabellen stehen vor den Tabellen, auf die sie zeigen; CASCADE nimmt Fremdschluessel mit.

Modul 1 Leitstand: order_lines, orders, stock, customers.
Modul 2 Planung: bom_lines, routing_steps, articles, materials, plant_settings.
Modul 3 Standortplan und Hallen-Baukasten: hall_flows, site_flows; dazu die Spalten halls.kind,
halls.site_x/site_y/site_w/site_h (Lage im Standortplan) und machines.pos_x/pos_y (Kachel in der Halle).

Revision ID: 0005_nebenmodule_entfernen
Revises: 0004_stoerfall_felder
Create Date: 2026-10-02
"""

from alembic import op

revision = "0005_nebenmodule_entfernen"
down_revision = "0004_stoerfall_felder"
branch_labels = None
depends_on = None

# Reihenfolge: abhaengige Tabellen zuerst (order_lines vor orders, stock vor articles-Verweis, orders vor customers;
# bom_lines und routing_steps vor articles und materials; hall_flows und site_flows zeigen nur auf halls/machines)
DROPPED = [
    "order_lines",
    "orders",
    "stock",
    "customers",
    "bom_lines",
    "routing_steps",
    "articles",
    "materials",
    "plant_settings",
    "hall_flows",
    "site_flows",
]

# (Tabelle, Spalte): Spalten der entfernten Module auf Tabellen, die bleiben
DROPPED_COLUMNS = [
    ("halls", "kind"),
    ("halls", "site_x"),
    ("halls", "site_y"),
    ("halls", "site_w"),
    ("halls", "site_h"),
    ("machines", "pos_x"),
    ("machines", "pos_y"),
]


def upgrade() -> None:
    for table in DROPPED:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for table, column in DROPPED_COLUMNS:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")


def downgrade() -> None:
    # Die Tabellen und Spalten der entfernten Module kommen nicht zurueck: ihr Modell und ihr Code sind
    # geloescht, eine Wiederherstellung waere ein leeres Schema ohne Nutzer. Downgrade stoppt bei 0004.
    pass
