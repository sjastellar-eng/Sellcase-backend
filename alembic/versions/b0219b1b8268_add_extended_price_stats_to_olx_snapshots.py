"""add extended price stats to olx_snapshots

Revision ID: b0219b1b8268
Revises: c41c5034a759
Create Date: 2026-01-13
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b0219b1b8268"
down_revision = "c41c5034a759"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("olx_snapshots", sa.Column("median_price", sa.Float(), nullable=True))
    op.add_column("olx_snapshots", sa.Column("p25_price", sa.Float(), nullable=True))
    op.add_column("olx_snapshots", sa.Column("p75_price", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("olx_snapshots", "p75_price")
    op.drop_column("olx_snapshots", "p25_price")
    op.drop_column("olx_snapshots", "median_price")
