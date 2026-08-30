"""add chunk full-text search index

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_document_chunks_content_fts ON document_chunks "
        "USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_fts")
