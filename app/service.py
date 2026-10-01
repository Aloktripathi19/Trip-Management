import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import repository
from app.enums import DELETABLE_STATUSES, TripStatus, can_transition
from app.exceptions import (
    DriverRequired,
    DuplicateTripNumber,
    InvalidStatusTransition,
    TripNotDeletable,
    TripNotFound,
)
from app.models import Trip
from app.schemas import TripCreate, TripStatusUpdate


def create_trip(db: Session, data: TripCreate) -> Trip:
    """Create a trip.

    Duplicates are rejected with 409 DUPLICATE_TRIP_NUMBER. The unique index on
    trip_number is the source of truth (not a read-then-insert check), so this
    stays correct when two identical requests race each other.
    """
    trip = Trip(
        trip_number=data.trip_number,
        source=data.source,
        destination=data.destination,
        driver_name=data.driver_name,
        status=TripStatus.CREATED.value,
    )
    db.add(trip)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Duplicate (or lost a race): confirm it was the trip_number constraint.
        if repository.get_by_trip_number(db, data.trip_number):
            raise DuplicateTripNumber(
                f"A trip with trip_number '{data.trip_number}' already exists",
                details={"field": "trip_number"},
            )
        raise
    db.refresh(trip)
    return trip


def get_trip(db: Session, trip_id: uuid.UUID) -> Trip:
    trip = repository.get_by_id(db, trip_id)
    if trip is None:
        raise TripNotFound(f"Trip '{trip_id}' not found")
    return trip


def list_trips(
    db: Session, *, status: TripStatus | None, page: int, page_size: int
) -> tuple[list[Trip], int]:
    return repository.list_trips(
        db, status=status.value if status else None, page=page, page_size=page_size
    )


def update_status(db: Session, trip_id: uuid.UUID, data: TripStatusUpdate) -> Trip:
    """Move a trip along the state machine.

    The row is locked with SELECT ... FOR UPDATE before the current status is
    read, so the check-then-write is atomic per trip. Of two simultaneous
    requests, the second waits, then re-validates against the *new* status and
    is rejected with 409 if the transition is no longer legal.
    """
    try:
        trip = repository.get_by_id(db, trip_id, for_update=True)
        if trip is None:
            raise TripNotFound(f"Trip '{trip_id}' not found")

        current = TripStatus(trip.status)
        target = data.status

        if not can_transition(current, target):
            raise InvalidStatusTransition(
                f"Cannot transition from {current.value} to {target.value}",
                details={
                    "current_status": current.value,
                    "requested_status": target.value,
                },
            )

        if target is TripStatus.ASSIGNED:
            driver = data.driver_name or trip.driver_name
            if not driver:
                raise DriverRequired("driver_name is required to assign a trip")
            trip.driver_name = driver

        trip.status = target.value
        db.commit()
    except Exception:
        db.rollback()  # releases the row lock
        raise
    db.refresh(trip)
    return trip


def delete_trip(db: Session, trip_id: uuid.UUID) -> None:
    try:
        trip = repository.get_by_id(db, trip_id, for_update=True)
        if trip is None:
            raise TripNotFound(f"Trip '{trip_id}' not found")
        if TripStatus(trip.status) not in DELETABLE_STATUSES:
            raise TripNotDeletable(
                f"Trips in status {trip.status} cannot be deleted; "
                "cancel the trip first or delete only CREATED/CANCELLED trips",
                details={"current_status": trip.status},
            )
        db.delete(trip)
        db.commit()
    except Exception:
        db.rollback()
        raise
