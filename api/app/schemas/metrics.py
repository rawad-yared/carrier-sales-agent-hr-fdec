from pydantic import BaseModel


class MetricsSummaryResponse(BaseModel):
    total_calls: int
    outcomes: dict[str, int]
    sentiment: dict[str, int]
    acceptance_rate: float
    avg_negotiation_rounds: float
    avg_delta_from_loadboard: float
    total_booked_revenue: float
