from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

OUTCOMES = (
    "booked",
    "carrier_declined",
    "broker_declined",
    "no_match",
    "carrier_ineligible",
    "abandoned",
    "error",
)
SENTIMENTS = ("positive", "neutral", "negative")
ACTIONS = ("accept", "counter", "reject")
LOAD_STATUSES = ("available", "booked", "expired")


class Load(Base):
    __tablename__ = "loads"

    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    equipment_type: Mapped[str] = mapped_column(Text, nullable=False)
    loadboard_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[int | None] = mapped_column(Integer)
    commodity_type: Mapped[str | None] = mapped_column(Text)
    num_of_pieces: Mapped[int | None] = mapped_column(Integer)
    miles: Mapped[int | None] = mapped_column(Integer)
    dimensions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="available")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"status IN {LOAD_STATUSES}", name="loads_status_check"),
        Index("ix_loads_equipment_type", "equipment_type"),
        Index("ix_loads_pickup_datetime", "pickup_datetime"),
        Index("ix_loads_origin", "origin"),
        Index("ix_loads_destination", "destination"),
        Index("ix_loads_status", "status"),
    )


class Carrier(Base):
    __tablename__ = "carriers"

    mc_number: Mapped[str] = mapped_column(Text, primary_key=True)
    carrier_name: Mapped[str | None] = mapped_column(Text)
    dot_number: Mapped[str | None] = mapped_column(Text)
    allowed_to_operate: Mapped[str | None] = mapped_column(Text)
    raw_fmcsa_response: Mapped[dict | None] = mapped_column(JSONB)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Call(Base):
    __tablename__ = "calls"

    call_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    mc_number: Mapped[str | None] = mapped_column(Text)
    carrier_name: Mapped[str | None] = mapped_column(Text)
    load_id: Mapped[str | None] = mapped_column(Text, ForeignKey("loads.load_id"))
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str] = mapped_column(Text, nullable=False)
    final_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    negotiation_rounds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        Computed("(EXTRACT(EPOCH FROM ended_at - started_at))::INT", persisted=True),
    )
    transcript: Mapped[str | None] = mapped_column(Text)
    extracted: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"outcome IN {OUTCOMES}", name="calls_outcome_check"),
        CheckConstraint(f"sentiment IN {SENTIMENTS}", name="calls_sentiment_check"),
        Index("ix_calls_outcome", "outcome"),
        Index("ix_calls_started_at_desc", "started_at"),
        Index("ix_calls_sentiment", "sentiment"),
        Index("ix_calls_load_id", "load_id"),
    )


class Negotiation(Base):
    __tablename__ = "negotiations"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    load_id: Mapped[str] = mapped_column(Text, ForeignKey("loads.load_id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    carrier_offer: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    counter_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    reasoning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"action IN {ACTIONS}", name="negotiations_action_check"),
        CheckConstraint("round_number BETWEEN 1 AND 3", name="negotiations_round_check"),
        Index("ix_negotiations_session_id", "session_id"),
    )
