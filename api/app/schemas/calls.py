import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DATETIME_FALLBACK_FORMATS = (
    "%A, %B %d, %Y %I:%M:%S %p UTC",
    "%A, %B %d, %Y %I:%M:%S %p",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %I:%M:%S %p",
)


def _parse_flexible_datetime(value: Any) -> Any:
    """Accept ISO 8601 or common human-readable formats (HappyRobot's
    'Now (UTC)' variable emits 'Monday, April 13, 2026 07:36:05 PM UTC').
    Returns a datetime or the original value so Pydantic can still try.
    """
    if value is None or isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in _DATETIME_FALLBACK_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return value  # let Pydantic emit its own error if none matched


def _coerce_transcript(value: Any) -> Any:
    """HappyRobot's transcript variable is a list of message dicts like
    [{'role': 'assistant', 'content': '...'}, {'role': 'user', 'content': '...'}].
    Flatten it to plain text. Strings pass through. Null passes through.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, list):
        lines: list[str] = []
        for msg in value:
            if not isinstance(msg, dict):
                lines.append(str(msg))
                continue
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, (dict, list)):
                content = json.dumps(content, default=str)
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    return str(value)

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

    # coerce_numbers_to_str: HR's LLM sometimes sends mc_number / load_id /
    # session_id as JSON numbers. Accept and cast to str.
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

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

    @field_validator("started_at", "ended_at", mode="before")
    @classmethod
    def _flex_datetime(cls, v: Any) -> Any:
        return _parse_flexible_datetime(v)

    @field_validator("transcript", mode="before")
    @classmethod
    def _flatten_transcript(cls, v: Any) -> Any:
        return _coerce_transcript(v)


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


class NegotiationRoundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    round_number: int
    carrier_offer: Decimal
    action: str
    counter_price: Decimal | None = None
    reasoning: str | None = None
    created_at: datetime


class CallNegotiationsResponse(BaseModel):
    call_id: str
    session_id: str
    load_id: str | None = None
    rounds: list[NegotiationRoundOut]
