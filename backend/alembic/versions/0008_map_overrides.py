"""Tabelle map_overrides: menschliche Korrekturen am Maschinenmodell.

Revision ID: 0008_map_overrides
Revises: 0007_machine_notes
Create Date: 2026-11-05
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_map_overrides"
down_revision = "0007_machine_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "map_overrides",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), server_default="default", nullable=False),
        sa.Column("machine_id", sa.String(length=32), nullable=False),
        sa.Column("tag", sa.String(length=120), nullable=False),
        sa.Column("zone_code", sa.String(length=120), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine_id", "tag"),
    )
    op.create_index(op.f("ix_map_overrides_workspace_id"), "map_overrides", ["workspace_id"])
    op.create_index(op.f("ix_map_overrides_machine_id"), "map_overrides", ["machine_id"])


def downgrade() -> None:
    op.drop_table("map_overrides")
