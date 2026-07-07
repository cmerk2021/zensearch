"""add user.ai_enabled

Revision ID: a1b2c3d4e5f6
Revises: 4663645b3f8c
Create Date: 2026-07-07 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '4663645b3f8c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'ai_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'ai_enabled')
