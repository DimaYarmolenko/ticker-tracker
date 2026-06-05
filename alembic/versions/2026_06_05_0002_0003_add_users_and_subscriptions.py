"""add users and user_tickers tables

Revision ID: 0003_add_users_and_subscriptions
Revises: 0002_add_article_evaluation
Create Date: 2026-06-05

Introduces multi-user support: a ``users`` table for authentication and a
``user_tickers`` join table representing per-user ticker subscriptions. The
existing ``tickers``, ``articles``, ``article_tickers`` and ``prices`` tables
remain global; unsubscribing only deletes the join row.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003_add_users_and_subscriptions"
down_revision: Union[str, None] = "0002_add_article_evaluation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "user_tickers",
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ticker_id",
            sa.String(length=36),
            sa.ForeignKey("tickers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("subscribed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_tickers_user", "user_tickers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_tickers_user", table_name="user_tickers")
    op.drop_table("user_tickers")
    op.drop_table("users")
