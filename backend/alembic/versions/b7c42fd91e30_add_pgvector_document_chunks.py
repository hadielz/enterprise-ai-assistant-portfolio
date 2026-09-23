"""add pgvector document chunks

Revision ID: b7c42fd91e30
Revises: a18d7c9e4f21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "b7c42fd91e30"
down_revision: Union[str, None] = "a18d7c9e4f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "chunk_id",
            name="uq_document_chunks_source_chunk_id",
        ),
    )
    op.create_index(
        op.f("ix_document_chunks_source"),
        "document_chunks",
        ["source"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_l2_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_index(op.f("ix_document_chunks_source"), table_name="document_chunks")
    op.drop_table("document_chunks")
    # Do not DROP EXTENSION vector: another schema/table may depend on it.
