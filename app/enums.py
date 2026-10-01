from enum import Enum


class TripStatus(str, Enum):
    CREATED = "CREATED"
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# State machine: current status -> statuses it may move to.
# COMPLETED and CANCELLED are terminal (empty sets).
ALLOWED_TRANSITIONS: dict[TripStatus, frozenset[TripStatus]] = {
    TripStatus.CREATED: frozenset({TripStatus.ASSIGNED, TripStatus.CANCELLED}),
    TripStatus.ASSIGNED: frozenset({TripStatus.IN_TRANSIT, TripStatus.CANCELLED}),
    TripStatus.IN_TRANSIT: frozenset({TripStatus.COMPLETED, TripStatus.CANCELLED}),
    TripStatus.COMPLETED: frozenset(),
    TripStatus.CANCELLED: frozenset(),
}

# Trips in these statuses may be hard-deleted.
DELETABLE_STATUSES: frozenset[TripStatus] = frozenset(
    {TripStatus.CREATED, TripStatus.CANCELLED}
)


def can_transition(current: TripStatus, target: TripStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
