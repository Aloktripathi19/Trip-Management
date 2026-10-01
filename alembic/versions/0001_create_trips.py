"""create trips table

Revision ID: 0001_create_trips
Revises:
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_create_trips"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_number", sa.String(50), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("driver_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="CREATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('CREATED', 'ASSIGNED', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED')",
            name="ck_trips_status",
        ),
        sa.CheckConstraint("source <> destination", name="ck_trips_source_ne_dest"),
        sa.CheckConstraint("length(trim(trip_number)) > 0", name="ck_trips_number_not_blank"),
    )

    # Uniqueness of trip_number is enforced by the database, not just the app.
    op.create_index("uq_trips_trip_number", "trips", ["trip_number"], unique=True)

    # GET /trips?status=X ordered by created_at.
    op.create_index("ix_trips_status_created_at", "trips", ["status", "created_at"])
    op.create_index("ix_trips_created_at", "trips", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_trips_created_at", table_name="trips")
    op.drop_index("ix_trips_status_created_at", table_name="trips")
    op.drop_index("uq_trips_trip_number", table_name="trips")
    op.drop_table("trips")
