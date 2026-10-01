import uuid

import pytest


def assert_error(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    return body["error"]


# ---------------------------------------------------------------- create
def test_create_trip(client):
    resp = client.post(
        "/trips", json={"trip_number": " T-1 ", "source": "Delhi", "destination": "Pune"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert resp.headers["Location"] == f"/trips/{body['id']}"
    assert body["trip_number"] == "T-1"  # whitespace trimmed
    assert body["status"] == "CREATED"
    assert body["driver_name"] is None
    assert body["created_at"] and body["updated_at"]
    uuid.UUID(body["id"])


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"trip_number": "T-1", "source": "A"},
        {"trip_number": "", "source": "A", "destination": "B"},
        {"trip_number": "   ", "source": "A", "destination": "B"},
        {"trip_number": "bad number!", "source": "A", "destination": "B"},
        {"trip_number": "T" * 51, "source": "A", "destination": "B"},
        {"trip_number": "T-1", "source": "", "destination": "B"},
        {"trip_number": "T-1", "source": "A", "destination": "a"},  # same, case-insensitive
        {"trip_number": "T-1", "source": "A", "destination": "B", "driver_name": " "},
        {"trip_number": "T-1", "source": "A", "destination": "B", "status": "COMPLETED"},
        {"trip_number": 123, "source": "A", "destination": "B"},
    ],
)
def test_create_validation_errors(client, payload):
    err = assert_error(client.post("/trips", json=payload), 422, "VALIDATION_ERROR")
    assert err["details"]


def test_create_duplicate_trip_number(client, make_trip):
    make_trip(trip_number="DUP-1")
    resp = client.post(
        "/trips", json={"trip_number": "DUP-1", "source": "X", "destination": "Y"}
    )
    assert_error(resp, 409, "DUPLICATE_TRIP_NUMBER")


# ------------------------------------------------------------------- get
def test_get_trip(client, make_trip):
    trip = make_trip()
    resp = client.get(f"/trips/{trip['id']}")
    assert resp.status_code == 200
    assert resp.json() == trip


def test_get_trip_not_found(client):
    assert_error(client.get(f"/trips/{uuid.uuid4()}"), 404, "TRIP_NOT_FOUND")


def test_get_trip_invalid_uuid(client):
    assert_error(client.get("/trips/not-a-uuid"), 422, "VALIDATION_ERROR")


# ------------------------------------------------------------------ list
def test_list_pagination(client, make_trip):
    for _ in range(5):
        make_trip()
    r1 = client.get("/trips", params={"page": 1, "page_size": 2}).json()
    r2 = client.get("/trips", params={"page": 2, "page_size": 2}).json()
    r3 = client.get("/trips", params={"page": 3, "page_size": 2}).json()
    assert r1["meta"] == {"page": 1, "page_size": 2, "total_items": 5, "total_pages": 3}
    assert [len(r["items"]) for r in (r1, r2, r3)] == [2, 2, 1]
    ids = [t["id"] for r in (r1, r2, r3) for t in r["items"]]
    assert len(set(ids)) == 5  # no duplicates / gaps across pages


def test_list_newest_first(client, make_trip):
    a, b = make_trip(), make_trip()
    items = client.get("/trips").json()["items"]
    assert [t["id"] for t in items] == [b["id"], a["id"]]


def test_list_page_beyond_end_is_empty(client, make_trip):
    make_trip()
    body = client.get("/trips", params={"page": 9}).json()
    assert body["items"] == []
    assert body["meta"]["total_items"] == 1


def test_list_filter_by_status(client, make_trip):
    a, b, c = make_trip(), make_trip(), make_trip()
    client.patch(f"/trips/{a['id']}/status", json={"status": "ASSIGNED", "driver_name": "Ravi"})
    client.patch(f"/trips/{b['id']}/status", json={"status": "CANCELLED"})
    created = client.get("/trips", params={"status": "CREATED"}).json()
    assert [t["id"] for t in created["items"]] == [c["id"]]
    assert client.get("/trips", params={"status": "ASSIGNED"}).json()["meta"]["total_items"] == 1
    assert client.get("/trips", params={"status": "COMPLETED"}).json()["meta"]["total_items"] == 0


@pytest.mark.parametrize(
    "params",
    [{"status": "BOGUS"}, {"page": 0}, {"page_size": 0}, {"page_size": 101}, {"page": "x"}],
)
def test_list_invalid_params(client, params):
    assert_error(client.get("/trips", params=params), 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------- status
def patch(client, trip_id, **body):
    return client.patch(f"/trips/{trip_id}/status", json=body)


def test_full_happy_path(client, make_trip):
    trip = make_trip()
    r = patch(client, trip["id"], status="ASSIGNED", driver_name="Ravi")
    assert r.status_code == 200 and r.json()["driver_name"] == "Ravi"
    assert patch(client, trip["id"], status="IN_TRANSIT").json()["status"] == "IN_TRANSIT"
    done = patch(client, trip["id"], status="COMPLETED").json()
    assert done["status"] == "COMPLETED"
    assert done["updated_at"] >= trip["updated_at"]


def test_assign_uses_existing_driver(client, make_trip):
    trip = make_trip(driver_name="Asha")
    assert patch(client, trip["id"], status="ASSIGNED").status_code == 200


def test_assign_requires_driver(client, make_trip):
    trip = make_trip()
    assert_error(patch(client, trip["id"], status="ASSIGNED"), 422, "DRIVER_REQUIRED")
    assert client.get(f"/trips/{trip['id']}").json()["status"] == "CREATED"


def test_driver_name_rejected_for_other_statuses(client, make_trip):
    trip = make_trip()
    assert_error(
        patch(client, trip["id"], status="CANCELLED", driver_name="X"), 422, "VALIDATION_ERROR"
    )


def test_cannot_skip_states(client, make_trip):
    trip = make_trip()
    err = assert_error(patch(client, trip["id"], status="COMPLETED"), 409, "INVALID_STATUS_TRANSITION")
    assert err["details"] == {"current_status": "CREATED", "requested_status": "COMPLETED"}
    assert_error(patch(client, trip["id"], status="IN_TRANSIT"), 409, "INVALID_STATUS_TRANSITION")


def test_cannot_move_backwards(client, make_trip):
    trip = make_trip()
    patch(client, trip["id"], status="ASSIGNED", driver_name="Ravi")
    patch(client, trip["id"], status="IN_TRANSIT")
    assert_error(patch(client, trip["id"], status="ASSIGNED"), 409, "INVALID_STATUS_TRANSITION")
    assert_error(patch(client, trip["id"], status="CREATED"), 409, "INVALID_STATUS_TRANSITION")


def test_same_status_is_rejected(client, make_trip):
    trip = make_trip()
    assert_error(patch(client, trip["id"], status="CREATED"), 409, "INVALID_STATUS_TRANSITION")


@pytest.mark.parametrize("terminal", ["COMPLETED", "CANCELLED"])
@pytest.mark.parametrize("target", ["CREATED", "ASSIGNED", "IN_TRANSIT", "COMPLETED", "CANCELLED"])
def test_terminal_states_are_final(client, make_trip, terminal, target):
    trip = make_trip(driver_name="Ravi")
    if terminal == "CANCELLED":
        patch(client, trip["id"], status="CANCELLED")
    else:
        patch(client, trip["id"], status="ASSIGNED")
        patch(client, trip["id"], status="IN_TRANSIT")
        patch(client, trip["id"], status="COMPLETED")
    body = {"status": target}
    if target == "ASSIGNED":
        body["driver_name"] = "Other"
    assert_error(patch(client, trip["id"], **body), 409, "INVALID_STATUS_TRANSITION")


def test_status_update_errors(client):
    assert_error(patch(client, uuid.uuid4(), status="ASSIGNED", driver_name="x"), 404, "TRIP_NOT_FOUND")
    assert_error(patch(client, uuid.uuid4(), status="NOPE"), 422, "VALIDATION_ERROR")
    assert_error(client.patch(f"/trips/{uuid.uuid4()}/status", json={}), 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------- delete
def test_delete_created_trip(client, make_trip):
    trip = make_trip()
    assert client.delete(f"/trips/{trip['id']}").status_code == 204
    assert_error(client.get(f"/trips/{trip['id']}"), 404, "TRIP_NOT_FOUND")


def test_delete_cancelled_trip(client, make_trip):
    trip = make_trip()
    patch(client, trip["id"], status="CANCELLED")
    assert client.delete(f"/trips/{trip['id']}").status_code == 204


@pytest.mark.parametrize("stage", ["ASSIGNED", "IN_TRANSIT", "COMPLETED"])
def test_delete_blocked_for_active_or_completed(client, make_trip, stage):
    trip = make_trip(driver_name="Ravi")
    for step in ["ASSIGNED", "IN_TRANSIT", "COMPLETED"]:
        patch(client, trip["id"], status=step)
        if step == stage:
            break
    assert_error(client.delete(f"/trips/{trip['id']}"), 409, "TRIP_NOT_DELETABLE")
    assert client.get(f"/trips/{trip['id']}").status_code == 200


def test_delete_not_found(client):
    assert_error(client.delete(f"/trips/{uuid.uuid4()}"), 404, "TRIP_NOT_FOUND")


# ------------------------------------------------------- misc / errors
def test_unknown_route_uses_error_envelope(client):
    assert_error(client.get("/nope"), 404, "NOT_FOUND")


def test_method_not_allowed_uses_error_envelope(client):
    assert_error(client.put("/trips"), 405, "METHOD_NOT_ALLOWED")


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
