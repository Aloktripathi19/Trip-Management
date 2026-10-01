import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app import service
from app.config import get_settings
from app.database import get_db
from app.enums import TripStatus
from app.schemas import (
    ErrorResponse,
    Page,
    PageMeta,
    TripCreate,
    TripResponse,
    TripStatusUpdate,
)

router = APIRouter(prefix="/trips", tags=["trips"])

DB = Annotated[Session, Depends(get_db)]

_errors = {
    404: {"model": ErrorResponse, "description": "Trip not found"},
    409: {"model": ErrorResponse, "description": "Conflict"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.post(
    "",
    response_model=TripResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: _errors[409], 422: _errors[422]},
)
def create_trip(payload: TripCreate, response: Response, db: DB):
    trip = service.create_trip(db, payload)
    response.headers["Location"] = f"/trips/{trip.id}"
    return trip


@router.get("", response_model=Page[TripResponse], responses={422: _errors[422]})
def list_trips(
    db: DB,
    status_filter: Annotated[
        TripStatus | None, Query(alias="status", description="Filter by trip status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=get_settings().max_page_size)] = get_settings().default_page_size,
):
    items, total = service.list_trips(db, status=status_filter, page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size
    return Page[TripResponse](
        items=items,
        meta=PageMeta(page=page, page_size=page_size, total_items=total, total_pages=total_pages),
    )


@router.get("/{trip_id}", response_model=TripResponse, responses={404: _errors[404], 422: _errors[422]})
def get_trip(trip_id: uuid.UUID, db: DB):
    return service.get_trip(db, trip_id)


@router.patch("/{trip_id}/status", response_model=TripResponse, responses=_errors)
def update_trip_status(trip_id: uuid.UUID, payload: TripStatusUpdate, db: DB):
    return service.update_status(db, trip_id, payload)


@router.delete(
    "/{trip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: _errors[404], 409: _errors[409], 422: _errors[422]},
)
def delete_trip(trip_id: uuid.UUID, db: DB):
    service.delete_trip(db, trip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
