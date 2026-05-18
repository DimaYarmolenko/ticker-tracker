"""add article evaluation columns

Revision ID: 0002_add_article_evaluation
Revises: 0001_baseline
Create Date: 2026-05-11

Adds importance / evaluated_at / evaluator_version on ``articles`` and
impact / impact_confidence on ``article_tickers``. Uses ``IF NOT EXISTS`` so
the migration is idempotent against databases where ``Base.metadata.create_all``
already added the columns.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_add_article_evaluation"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS importance INTEGER")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMP")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS evaluator_version VARCHAR(40)")
    op.execute("ALTER TABLE article_tickers ADD COLUMN IF NOT EXISTS impact VARCHAR(16)")
    op.execute(
        "ALTER TABLE article_tickers ADD COLUMN IF NOT EXISTS impact_confidence DOUBLE PRECISION"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE article_tickers DROP COLUMN IF EXISTS impact_confidence")
    op.execute("ALTER TABLE article_tickers DROP COLUMN IF EXISTS impact")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS evaluator_version")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS evaluated_at")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS importance")
