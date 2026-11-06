"""Spalte cabinet_images.location_code: Einbauort des Schranks (+ST1) als Zone des Maschinenmodells.

Revision ID: 0009_cabinet_location_code
Revises: 0008_map_overrides
Create Date: 2026-11-06
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_cabinet_location_code"
down_revision = "0008_map_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cabinet_images", sa.Column("location_code", sa.String(length=120), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("cabinet_images", "location_code")
