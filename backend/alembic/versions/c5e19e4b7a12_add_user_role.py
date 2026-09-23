"""add user role

Revision ID: c5e19e4b7a12
Revises: 2505a536463c
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e19e4b7a12"
down_revision: Union[str, Sequence[str], None] = "2505a536463c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the minimum R1 authorization role to existing and future users."""

    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="employee",
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('employee', 'support')",
    )


def downgrade() -> None:
    """Remove the R1 user role."""

    op.drop_constraint(
        "ck_users_role",
        "users",
        type_="check",
    )
    op.drop_column("users", "role")
