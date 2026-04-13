from pydantic import BaseModel, ConfigDict


class VerifyCarrierRequest(BaseModel):
    # LLMs in HappyRobot's tool-calling layer sometimes send mc_number as a
    # JSON number (e.g. 123456) instead of a string. Coerce defensively —
    # mc_number is always treated as an opaque identifier downstream.
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    mc_number: str


class VerifyCarrierResponse(BaseModel):
    eligible: bool
    mc_number: str
    carrier_name: str | None = None
    dot_number: str | None = None
    allowed_to_operate: str | None = None
    raw_fmcsa_status: str | None = None
    reason: str | None = None
