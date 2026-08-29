"""allow chunks before embedding

Revision ID: 0002
Revises: 0001
"""

import pgvector.sqlalchemy

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "document_chunks",
        "embedding",
        existing_type=pgvector.sqlalchemy.Vector(1024),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("DELETE FROM document_chunks WHERE embedding IS NULL")
    op.alter_column(
        "document_chunks",
        "embedding",
        existing_type=pgvector.sqlalchemy.Vector(1024),
        nullable=False,
    )
