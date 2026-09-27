"""Kostenbuch: ai_call_ledger je Workspace/Maschine/Zweck, Monatslimit am Workspace.

Revision ID: 0003_ai_call_ledger
Revises: 0002_workspaces
Create Date: 2026-09-28
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_ai_call_ledger"
down_revision = "0002_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("monthly_ai_cap_cents", sa.Integer(), nullable=True))
    op.create_table(
        "ai_call_ledger",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), server_default="default", nullable=False),
        sa.Column("machine_id", sa.String(length=32), nullable=True),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("images", sa.Integer(), nullable=False),
        sa.Column("cost_microcents", sa.BigInteger(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_call_ledger_workspace_id"), "ai_call_ledger", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_ai_call_ledger_machine_id"), "ai_call_ledger", ["machine_id"], unique=False)
    op.create_index(op.f("ix_ai_call_ledger_created_at"), "ai_call_ledger", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("ai_call_ledger")
    op.drop_column("workspaces", "monthly_ai_cap_cents")
