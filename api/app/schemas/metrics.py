from pydantic import BaseModel


class MetricsSummaryResponse(BaseModel):
    total_calls: int
    outcomes: dict[str, int]
    sentiment: dict[str, int]
    acceptance_rate: float
    avg_negotiation_rounds: float
    avg_delta_from_loadboard: float
    total_booked_revenue: float
    # Agent-impact fields (what's the agent worth to the business?)
    total_duration_seconds: int
    estimated_rep_hours_saved: float
    estimated_labor_cost_saved_usd: float
    labor_cost_per_hour_usd: float
    # Recoverable-decline signal (what should ops do next?)
    recoverable_declines: int
    # Sentiment-aware acceptance (where is the agent winning/losing on tone?)
    acceptance_rate_by_sentiment: dict[str, float]


class EquipmentBreakdownRow(BaseModel):
    equipment_type: str
    calls: int
    booked: int
    acceptance_rate: float
    avg_delta_from_loadboard: float
    avg_rounds_to_book: float
    booked_revenue: float


class MetricsByEquipmentResponse(BaseModel):
    results: list[EquipmentBreakdownRow]
