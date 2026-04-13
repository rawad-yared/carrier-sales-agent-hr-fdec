from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class EvaluateOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    load_id: str
    carrier_offer: Decimal
    round_number: int
    session_id: str


class EvaluateOfferResponse(BaseModel):
    action: str
    counter_price: Decimal | None = None
    round_number: int
    reasoning: str
    final: bool
