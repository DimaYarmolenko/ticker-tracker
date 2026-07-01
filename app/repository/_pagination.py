from sqlalchemy import Select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session


def paginate(
    db: Session,
    base_stmt: Select,
    count_stmt: Select,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Row], int]:
    """Run an offset/limit page while computing the total in a single round-trip.

    `base_stmt` selects the page entities (with ordering, joins, filters) but no
    limit/offset; `count_stmt` is the matching `select(func.count(...))`. The total
    is embedded as a scalar subquery column so it comes back with the rows; when the
    offset lands past the end (no rows) the count is fetched with a fallback query.

    Returns the result rows with the total column stripped off — each caller unpacks
    its own entity shape — plus the total count.
    """
    count_sub = count_stmt.scalar_subquery()
    stmt = base_stmt.add_columns(count_sub.label("total")).offset(offset).limit(limit)
    rows = db.execute(stmt).all()
    if rows:
        total = rows[0][-1]
        return [row[:-1] for row in rows], total
    total = db.scalar(count_stmt)
    return [], total or 0
