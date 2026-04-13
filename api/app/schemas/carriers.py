from pydantic import BaseModel, ConfigDict


class VerifyCarrierRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mc_number: str


class VerifyCarrierResponse(BaseModel):
    eligible: bool
    mc_number: str
    carrier_name: str | None = None
    dot_number: str | None = None
    allowed_to_operate: str | None = None
    raw_fmcsa_status: str | None = None
    reason: str | None = None
