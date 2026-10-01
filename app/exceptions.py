from typing import Any


class AppError(Exception):
    """Base class for domain errors; mapped to a consistent JSON error body."""

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: Any | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class TripNotFound(AppError):
    status_code = 404
    code = "TRIP_NOT_FOUND"


class DuplicateTripNumber(AppError):
    status_code = 409
    code = "DUPLICATE_TRIP_NUMBER"


class InvalidStatusTransition(AppError):
    status_code = 409
    code = "INVALID_STATUS_TRANSITION"


class TripNotDeletable(AppError):
    status_code = 409
    code = "TRIP_NOT_DELETABLE"


class DriverRequired(AppError):
    status_code = 422
    code = "DRIVER_REQUIRED"
