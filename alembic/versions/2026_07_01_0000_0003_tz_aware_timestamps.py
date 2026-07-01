"""tz aware timestamps

Revision ID: 0003_tz_aware_timestamps
Revises: 0002_add_article_evaluation
Create Date: 2026-07-01

Converts the four naive timestamp columns to ``TIMESTAMPTZ`` so the schema
matches the timezone-aware ``datetime.now(timezone.utc)`` defaults the app has
always inserted: ``tickers.date_added``, ``articles.published_at``,
``articles.fetched_at``, ``articles.evaluated_at``. (``prices.fetched_at`` was
already ``TIMESTAMPTZ``.) Existing naive values are interpreted as UTC.

Each ``ALTER`` is guarded on ``information_schema.columns.data_type`` so the
migration is idempotent — re-running it (or running it against a DB that already
has the tz-aware type) is a no-op, matching the convention of the earlier
revisions.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_tz_aware_timestamps"
down_revision: Union[str, None] = "0002_add_article_evaluation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) pairs to convert.
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("tickers", "date_added"),
    ("articles", "published_at"),
    ("articles", "fetched_at"),
    ("articles", "evaluated_at"),
)


def _convert(table: str, column: str, *, to_tz: bool) -> None:
    target_type = "timestamp with time zone" if to_tz else "timestamp without time zone"
    new_type = "TIMESTAMPTZ" if to_tz else "TIMESTAMP"
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = '{table}'
                  AND column_name = '{column}'
                  AND data_type <> '{target_type}'
            ) THEN
                ALTER TABLE {table}
                    ALTER COLUMN {column} TYPE {new_type} USING {column} AT TIME ZONE 'UTC';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    for table, column in _COLUMNS:
        _convert(table, column, to_tz=True)


def downgrade() -> None:
    for table, column in _COLUMNS:
        _convert(table, column, to_tz=False)
