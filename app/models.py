import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.enums import TripStatus

_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in TripStatus)


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    trip_number: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    driver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TripStatus.CREATED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_trips_status"),
        CheckConstraint("source <> destination", name="ck_trips_source_ne_dest"),
        CheckConstraint("length(trim(trip_number)) > 0", name="ck_trips_number_not_blank"),
        # Authoritative uniqueness guarantee, enforced by the database.
        Index("uq_trips_trip_number", "trip_number", unique=True),
        # Serves GET /trips?status=X ordered by newest first.
        Index("ix_trips_status_created_at", "status", "created_at"),
        Index("ix_trips_created_at", "created_at"),
    )
