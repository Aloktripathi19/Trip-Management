import uuid
from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.enums import TripStatus

TripNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50,
                           pattern=r"^[A-Za-z0-9][A-Za-z0-9._\-/]*$")
]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
DriverName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class TripCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_number: TripNumber
    source: Location
    destination: Location
    driver_name: DriverName | None = None

    @model_validator(mode="after")
    def source_and_destination_differ(self) -> "TripCreate":
        if self.source.casefold() == self.destination.casefold():
            raise ValueError("source and destination must be different")
        return self


class TripStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TripStatus
    # Needed when moving to ASSIGNED and no driver is set yet.
    driver_name: DriverName | None = None

    @model_validator(mode="after")
    def driver_only_when_assigning(self) -> "TripStatusUpdate":
        if self.driver_name is not None and self.status is not TripStatus.ASSIGNED:
            raise ValueError("driver_name can only be supplied when status is ASSIGNED")
        return self


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_number: str
    source: str
    destination: str
    driver_name: str | None
    status: TripStatus
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class PageMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list | dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


# Reusable query-param constraints
PageParam = Annotated[int, Field(ge=1)]
