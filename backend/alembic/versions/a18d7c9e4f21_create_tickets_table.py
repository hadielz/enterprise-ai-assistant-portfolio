"""create tickets table

Revision ID: a18d7c9e4f21
Revises: c5e19e4b7a12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a18d7c9e4f21"
down_revision: Union[str, Sequence[str], None] = "c5e19e4b7a12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(length=50), nullable=False),
        sa.Column("requester_user_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="created", nullable=False),
        sa.Column("action_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'in_progress', 'resolved')",
            name="ck_tickets_status",
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_action_id", "tickets", ["action_id"], unique=True)
    op.create_index("ix_tickets_public_id", "tickets", ["public_id"], unique=True)
    op.create_index(
        "ix_tickets_requester_user_id",
        "tickets",
        ["requester_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_requester_user_id", table_name="tickets")
    op.drop_index("ix_tickets_public_id", table_name="tickets")
    op.drop_index("ix_tickets_action_id", table_name="tickets")
    op.drop_table("tickets")
