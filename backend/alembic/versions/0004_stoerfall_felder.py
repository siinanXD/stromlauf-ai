"""Stoerfaelle: conversations bekommt outcome (open | resolved) und finding (Befund).

IF NOT EXISTS, damit die Revision auch auf einer Datenbank laeuft, die die Spalten schon hat. Der Standardwert gilt
auch fuer bestehende Zeilen: alte Chats sind offen und ohne Befund.

Revision ID: 0004_stoerfall_felder
Revises: 0003_ai_call_ledger
Create Date: 2026-10-01
"""

from alembic import op

revision = "0004_stoerfall_felder"
down_revision = "0003_ai_call_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS outcome VARCHAR(16) NOT NULL DEFAULT 'open'"
    )
    op.execute(
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS finding TEXT NOT NULL DEFAULT ''"
    )


def downgrade() -> None:
    op.drop_column("conversations", "finding")
    op.drop_column("conversations", "outcome")
