"""knowledge_chunks

Revision ID: 5a12d8b9c101
Revises: 2f6b2d7918be
Create Date: 2026-04-18 12:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5a12d8b9c101"
down_revision: str | Sequence[str] | None = "2f6b2d7918be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_tenant_id", "knowledge_chunks", ["tenant_id"])
    op.create_index(
        "ix_knowledge_chunks_tenant_document",
        "knowledge_chunks",
        ["tenant_id", "document_id"],
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding")
    op.drop_index("ix_knowledge_chunks_tenant_document", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_tenant_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
