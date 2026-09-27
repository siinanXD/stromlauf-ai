"""Mandanten: workspaces, users, workspace_members, login_tokens; workspace_id auf allen fachlichen Tabellen.

Vorhandene Zeilen landen im Workspace "default" (Standard); der gemeinsame API_KEY arbeitet weiter in
diesem Workspace. Siehe app/tenancy.py und app/auth.py.

Revision ID: 0002_workspaces
Revises: 0001_stromlauf_baseline
Create Date: 2026-09-27
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_workspaces"
down_revision = "0001_stromlauf_baseline"
branch_labels = None
depends_on = None

SCOPED_TABLES = [
    "knowledge_sources",
    "documents",
    "chunks",
    "tag_occurrences",
    "conversations",
    "halls",
    "machines",
    "hall_flows",
    "site_flows",
    "machine_specs",
    "fault_entries",
    "cabinet_images",
    "cabinet_hotspots",
    "machine_layouts",
    "layout_parts",
    "diagnosis_sessions",
]


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
    )
    op.create_table(
        "login_tokens",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_login_tokens_email"), "login_tokens", ["email"], unique=False)
    op.execute("INSERT INTO workspaces (id, name, created_at) VALUES ('default', 'Standard', now())")
    for table in SCOPED_TABLES:
        op.add_column(
            table,
            sa.Column("workspace_id", sa.String(length=32), nullable=False, server_default="default"),
        )
        op.create_foreign_key(
            f"fk_{table}_workspace_id", table, "workspaces", ["workspace_id"], ["id"], ondelete="CASCADE"
        )
        op.create_index(op.f(f"ix_{table}_workspace_id"), table, ["workspace_id"], unique=False)


def downgrade() -> None:
    for table in reversed(SCOPED_TABLES):
        op.drop_index(op.f(f"ix_{table}_workspace_id"), table_name=table)
        op.drop_constraint(f"fk_{table}_workspace_id", table, type_="foreignkey")
        op.drop_column(table, "workspace_id")
    op.drop_index(op.f("ix_login_tokens_email"), table_name="login_tokens")
    op.drop_table("login_tokens")
    op.drop_table("workspace_members")
    op.drop_table("users")
    op.drop_table("workspaces")
