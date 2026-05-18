"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-11

Bootstraps the base schema (tickers, articles, article_tickers, prices) for
fresh databases. For databases that predate Alembic adoption — where those
tables were already created by ``Base.metadata.create_all`` — this revision
detects their presence and is a no-op.
"""

from typing import Sequence, Union

from sqlalchemy import inspect

import app.models  # noqa: F401  -- register models with Base.metadata
from alembic import op
from app.database import Base

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BASE_TABLES = {"tickers", "articles", "article_tickers", "prices"}


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    missing = _BASE_TABLES - existing
    if not missing:
        return
    Base.metadata.create_all(
        bind=bind,
        tables=[t for t in Base.metadata.sorted_tables if t.name in missing],
    )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(
        bind=bind,
        tables=[t for t in Base.metadata.sorted_tables if t.name in _BASE_TABLES],
    )
