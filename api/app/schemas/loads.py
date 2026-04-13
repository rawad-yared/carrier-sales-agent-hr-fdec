from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LoadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    load_id: str
    origin: str
    destination: str
    pickup_datetime: datetime
    delivery_datetime: datetime
    equipment_type: str
    loadboard_rate: Decimal
    notes: str | None = None
    weight: int | None = None
    commodity_type: str | None = None
    num_of_pieces: int | None = None
    miles: int | None = None
    dimensions: str | None = None


class SearchLoadsRequest(BaseModel):
    # Defensive coercion for LLM-originated tool calls.
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    origin: str | None = None
    destination: str | None = None
    equipment_type: str | None = None
    pickup_date: date | None = None
    max_results: int = Field(default=3, ge=1, le=500)


class SearchLoadsResponse(BaseModel):
    results: list[LoadOut]
    count: int
