"""Tabelle machine_notes: belegte Sätze, die eine Maschine gelernt hat.

Revision ID: 0007_machine_notes
Revises: 0006_runs
Create Date: 2026-10-27
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_machine_notes"
down_revision = "0006_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "machine_notes",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), server_default="default", nullable=False),
        sa.Column("machine_id", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("quelle", sa.String(length=8), nullable=False),
        sa.Column("belege", sa.JSON(), nullable=False),
        sa.Column("gesperrt", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("conversation_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_machine_notes_workspace_id"), "machine_notes", ["workspace_id"])
    op.create_index(op.f("ix_machine_notes_machine_id"), "machine_notes", ["machine_id"])
    op.create_index(op.f("ix_machine_notes_created_at"), "machine_notes", ["created_at"])


def downgrade() -> None:
    op.drop_table("machine_notes")
