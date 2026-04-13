"""initial schema: loads, carriers, calls, negotiations

Revision ID: 0001
Revises:
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loads",
        sa.Column("load_id", sa.Text(), primary_key=True),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("pickup_datetime", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("delivery_datetime", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("equipment_type", sa.Text(), nullable=False),
        sa.Column("loadboard_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("weight", sa.Integer()),
        sa.Column("commodity_type", sa.Text()),
        sa.Column("num_of_pieces", sa.Integer()),
        sa.Column("miles", sa.Integer()),
        sa.Column("dimensions", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="available"),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('available','booked','expired')", name="loads_status_check"
        ),
    )
    op.create_index("ix_loads_equipment_type", "loads", ["equipment_type"])
    op.create_index("ix_loads_pickup_datetime", "loads", ["pickup_datetime"])
    op.create_index("ix_loads_origin", "loads", ["origin"])
    op.create_index("ix_loads_destination", "loads", ["destination"])
    op.create_index("ix_loads_status", "loads", ["status"])

    op.create_table(
        "carriers",
        sa.Column("mc_number", sa.Text(), primary_key=True),
        sa.Column("carrier_name", sa.Text()),
        sa.Column("dot_number", sa.Text()),
        sa.Column("allowed_to_operate", sa.Text()),
        sa.Column("raw_fmcsa_response", postgresql.JSONB()),
        sa.Column("last_checked_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "calls",
        sa.Column("call_id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False, unique=True),
        sa.Column("mc_number", sa.Text()),
        sa.Column("carrier_name", sa.Text()),
        sa.Column("load_id", sa.Text(), sa.ForeignKey("loads.load_id")),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.Text(), nullable=False),
        sa.Column("final_price", sa.Numeric(10, 2)),
        sa.Column("negotiation_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "duration_seconds",
            sa.Integer(),
            sa.Computed(
                "(EXTRACT(EPOCH FROM ended_at - started_at))::INT",
                persisted=True,
            ),
        ),
        sa.Column("transcript", sa.Text()),
        sa.Column("extracted", postgresql.JSONB()),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "outcome IN ('booked','carrier_declined','broker_declined','no_match',"
            "'carrier_ineligible','abandoned','error')",
            name="calls_outcome_check",
        ),
        sa.CheckConstraint(
            "sentiment IN ('positive','neutral','negative')", name="calls_sentiment_check"
        ),
    )
    op.create_index("ix_calls_outcome", "calls", ["outcome"])
    op.create_index("ix_calls_started_at_desc", "calls", [sa.text("started_at DESC")])
    op.create_index("ix_calls_sentiment", "calls", ["sentiment"])
    op.create_index("ix_calls_load_id", "calls", ["load_id"])

    op.create_table(
        "negotiations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("load_id", sa.Text(), sa.ForeignKey("loads.load_id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("carrier_offer", sa.Numeric(10, 2), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("counter_price", sa.Numeric(10, 2)),
        sa.Column("reasoning", sa.Text()),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "action IN ('accept','counter','reject')", name="negotiations_action_check"
        ),
        sa.CheckConstraint(
            "round_number BETWEEN 1 AND 3", name="negotiations_round_check"
        ),
    )
    op.create_index("ix_negotiations_session_id", "negotiations", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_negotiations_session_id", table_name="negotiations")
    op.drop_table("negotiations")
    op.drop_index("ix_calls_load_id", table_name="calls")
    op.drop_index("ix_calls_sentiment", table_name="calls")
    op.drop_index("ix_calls_started_at_desc", table_name="calls")
    op.drop_index("ix_calls_outcome", table_name="calls")
    op.drop_table("calls")
    op.drop_table("carriers")
    op.drop_index("ix_loads_status", table_name="loads")
    op.drop_index("ix_loads_destination", table_name="loads")
    op.drop_index("ix_loads_origin", table_name="loads")
    op.drop_index("ix_loads_pickup_datetime", table_name="loads")
    op.drop_index("ix_loads_equipment_type", table_name="loads")
    op.drop_table("loads")
