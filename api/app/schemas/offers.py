from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class EvaluateOfferRequest(BaseModel):
    # Defensive: LLMs sometimes stringify load_id/session_id or numericize
    # them. Coerce numbers->str; Pydantic handles the reverse already.
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

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
