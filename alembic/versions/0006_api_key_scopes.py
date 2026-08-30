"""add API key scopes

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "scopes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text('\'["read", "write"]\''),
        ),
    )
    op.alter_column("api_keys", "scopes", server_default=None)


def downgrade() -> None:
    op.drop_column("api_keys", "scopes")
