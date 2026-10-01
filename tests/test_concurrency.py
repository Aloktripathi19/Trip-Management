"""Concurrency tests. They need a real PostgreSQL (row locks / unique indexes)."""
import threading
from collections import Counter

from fastapi.testclient import TestClient

from app.main import app

WORKERS = 8


def run_concurrently(fn, n=WORKERS):
    """Run fn(i) in n threads released simultaneously; return the results."""
    barrier = threading.Barrier(n)
    results = [None] * n

    def worker(i):
        with TestClient(app) as c:  # own client per thread
            barrier.wait()
            results[i] = fn(c, i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


def test_concurrent_create_same_trip_number_creates_one(client):
    body = {"trip_number": "RACE-1", "source": "A", "destination": "B"}
    results = run_concurrently(lambda c, i: c.post("/trips", json=body).status_code)
    assert Counter(results) == {201: 1, 409: WORKERS - 1}
    assert client.get("/trips").json()["meta"]["total_items"] == 1


def test_concurrent_same_transition_only_one_wins(client, make_trip):
    trip = make_trip()
    payload = {"status": "ASSIGNED", "driver_name": "Ravi"}
    results = run_concurrently(
        lambda c, i: c.patch(f"/trips/{trip['id']}/status", json=payload).status_code
    )
    assert Counter(results) == {200: 1, 409: WORKERS - 1}
    assert client.get(f"/trips/{trip['id']}").json()["status"] == "ASSIGNED"


def test_concurrent_conflicting_transitions_leave_consistent_state(client, make_trip):
    """From ASSIGNED, IN_TRANSIT and CANCELLED race. Exactly one request may
    win and the stored status must be the winner's. If IN_TRANSIT wins first,
    CANCELLED is still legal afterwards, so both can succeed, but never in an
    order that breaks the state machine."""
    trip = make_trip(driver_name="Ravi")
    client.patch(f"/trips/{trip['id']}/status", json={"status": "ASSIGNED"})

    targets = ["IN_TRANSIT", "CANCELLED"] * (WORKERS // 2)
    results = run_concurrently(
        lambda c, i: (
            targets[i],
            c.patch(f"/trips/{trip['id']}/status", json={"status": targets[i]}).status_code,
        )
    )
    assert all(code in (200, 409) for _, code in results)
    wins = Counter(t for t, code in results if code == 200)

    # Each target can succeed at most once (a repeat is an illegal transition).
    assert 1 <= sum(wins.values()) <= 2
    assert all(n == 1 for n in wins.values())

    # CANCELLED is terminal, so if it won, it must have been applied last.
    final = client.get(f"/trips/{trip['id']}").json()["status"]
    assert final == ("CANCELLED" if "CANCELLED" in wins else "IN_TRANSIT")


def test_concurrent_complete_and_cancel_never_both_after_terminal(client, make_trip):
    trip = make_trip(driver_name="Ravi")
    for s in ("ASSIGNED", "IN_TRANSIT"):
        client.patch(f"/trips/{trip['id']}/status", json={"status": s})

    targets = ["COMPLETED", "CANCELLED"] * (WORKERS // 2)
    results = run_concurrently(
        lambda c, i: c.patch(f"/trips/{trip['id']}/status", json={"status": targets[i]}).status_code
    )
    # Both targets are terminal, so exactly one request can succeed.
    assert Counter(results) == {200: 1, 409: WORKERS - 1}
    assert client.get(f"/trips/{trip['id']}").json()["status"] in {"COMPLETED", "CANCELLED"}
