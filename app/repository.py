import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Trip


def get_by_id(db: Session, trip_id: uuid.UUID, *, for_update: bool = False) -> Trip | None:
    stmt = select(Trip).where(Trip.id == trip_id)
    if for_update:
        # Row-level lock (SELECT ... FOR UPDATE): concurrent writers on the same
        # trip queue up behind this transaction until it commits or rolls back.
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def get_by_trip_number(db: Session, trip_number: str) -> Trip | None:
    return db.execute(select(Trip).where(Trip.trip_number == trip_number)).scalar_one_or_none()


def list_trips(
    db: Session, *, status: str | None, page: int, page_size: int
) -> tuple[list[Trip], int]:
    filters = []
    if status is not None:
        filters.append(Trip.status == status)

    total = db.execute(select(func.count()).select_from(Trip).where(*filters)).scalar_one()

    items = (
        db.execute(
            select(Trip)
            .where(*filters)
            # id is a tie-breaker so pagination is stable for equal timestamps.
            .order_by(Trip.created_at.desc(), Trip.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(items), total
