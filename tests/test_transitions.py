import itertools

import pytest

from app.enums import ALLOWED_TRANSITIONS, TripStatus, can_transition

VALID = {
    (TripStatus.CREATED, TripStatus.ASSIGNED),
    (TripStatus.CREATED, TripStatus.CANCELLED),
    (TripStatus.ASSIGNED, TripStatus.IN_TRANSIT),
    (TripStatus.ASSIGNED, TripStatus.CANCELLED),
    (TripStatus.IN_TRANSIT, TripStatus.COMPLETED),
    (TripStatus.IN_TRANSIT, TripStatus.CANCELLED),
}


@pytest.mark.parametrize(
    "current,target", list(itertools.product(TripStatus, TripStatus))
)
def test_transition_matrix(current, target):
    assert can_transition(current, target) is ((current, target) in VALID)


def test_terminal_states_have_no_exits():
    assert ALLOWED_TRANSITIONS[TripStatus.COMPLETED] == frozenset()
    assert ALLOWED_TRANSITIONS[TripStatus.CANCELLED] == frozenset()
