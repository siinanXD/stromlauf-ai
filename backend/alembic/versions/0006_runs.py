"""Tabelle runs: ein Ablauf je Zeile, die sieben Schritte als JSON.

Revision ID: 0006_runs
Revises: 0005_nebenmodule_entfernen
Create Date: 2026-10-26
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_runs"
down_revision = "0005_nebenmodule_entfernen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), server_default="default", nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_id", sa.String(length=32), nullable=False),
        sa.Column("machine_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("trace_url", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runs_workspace_id"), "runs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_runs_source_id"), "runs", ["source_id"], unique=False)
    op.create_index(op.f("ix_runs_created_at"), "runs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("runs")
