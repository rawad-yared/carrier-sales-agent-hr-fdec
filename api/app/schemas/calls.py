from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Outcome = Literal[
    "booked",
    "carrier_declined",
    "broker_declined",
    "no_match",
    "carrier_ineligible",
    "abandoned",
    "error",
]
Sentiment = Literal["positive", "neutral", "negative"]


class LogCallRequest(BaseModel):
    """Body for POST /api/log-call.

    The HappyRobot log_call webhook sends: session_id, mc_number, carrier_name,
    load_id, outcome, sentiment, final_price, negotiation_rounds, ended_at,
    transcript, call_duration_seconds. It does NOT send started_at (HappyRobot
    doesn't expose call-start time as a variable) so the server computes it as
    ended_at - call_duration_seconds. The nested `extracted` object is also
    optional — HappyRobot will start sending it later.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    mc_number: str | None = None
    carrier_name: str | None = None
    load_id: str | None = None
    outcome: Outcome
    sentiment: Sentiment
    final_price: Decimal | None = None
    negotiation_rounds: int = Field(default=0, ge=0, le=3)
    started_at: datetime | None = None
    ended_at: datetime
    call_duration_seconds: float = Field(default=0.0, ge=0.0)
    transcript: str | None = None
    extracted: dict[str, Any] = Field(default_factory=dict)


class LogCallResponse(BaseModel):
    call_id: str
    status: Literal["logged", "updated"]


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_id: str
    session_id: str
    mc_number: str | None = None
    carrier_name: str | None = None
    load_id: str | None = None
    outcome: str
    sentiment: str
    final_price: Decimal | None = None
    negotiation_rounds: int
    started_at: datetime
    ended_at: datetime
    duration_seconds: int | None = None
    transcript: str | None = None
    extracted: dict[str, Any] | None = None


class CallsListResponse(BaseModel):
    results: list[CallOut]
    total: int
    limit: int
    offset: int
