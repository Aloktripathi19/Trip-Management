import os

# Point the app at the test database *before* the app modules are imported.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://trips:trips@localhost:5432/trips_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrate_database():
    """Build the schema with the real Alembic migration, not create_all()."""
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE trips"))
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_trip(client):
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        body = {
            "trip_number": f"TRIP-{counter['n']:04d}",
            "source": "Delhi",
            "destination": "Mumbai",
        }
        body.update(overrides)
        resp = client.post("/trips", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make
