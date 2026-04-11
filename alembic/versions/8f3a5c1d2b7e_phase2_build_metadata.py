"""phase2_build_metadata

Revision ID: 8f3a5c1d2b7e
Revises: 67f0237b4df9
Create Date: 2026-04-11 14:20:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8f3a5c1d2b7e"
down_revision: Union[str, Sequence[str], None] = "67f0237b4df9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("builds", sa.Column("requirements_id", sa.UUID(), nullable=True))
    op.add_column(
        "builds",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_foreign_key(
        "fk_builds_requirements_id_employee_requirements",
        "builds",
        "employee_requirements",
        ["requirements_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_builds_requirements_id", "builds", ["requirements_id"])
    op.alter_column("builds", "blueprint_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("builds", "blueprint_id", existing_type=sa.UUID(), nullable=False)
    op.drop_index("ix_builds_requirements_id", table_name="builds")
    op.drop_constraint("fk_builds_requirements_id_employee_requirements", "builds", type_="foreignkey")
    op.drop_column("builds", "metadata")
    op.drop_column("builds", "requirements_id")
