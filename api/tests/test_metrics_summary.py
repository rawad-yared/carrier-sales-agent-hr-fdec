from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def _log(
    client,
    session_id,
    outcome="booked",
    sentiment="positive",
    load_id="L-9001",
    final_price=None,
    negotiation_rounds=2,
    started_at="2026-04-13T14:00:00Z",
):
    payload = {
        "session_id": session_id,
        "outcome": outcome,
        "sentiment": sentiment,
        "load_id": load_id,
        "negotiation_rounds": negotiation_rounds,
        "started_at": started_at,
        "ended_at": "2026-04-13T14:05:00Z",
    }
    if final_price is not None:
        payload["final_price"] = final_price
    return client.post("/api/log-call", json=payload, headers=AUTH)


def test_metrics_empty(client):
    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total_calls"] == 0
    assert body["outcomes"]["booked"] == 0
    assert body["outcomes"]["no_match"] == 0
    assert body["sentiment"]["positive"] == 0
    assert body["acceptance_rate"] == 0.0
    assert body["avg_negotiation_rounds"] == 0.0
    assert body["avg_delta_from_loadboard"] == 0.0
    assert body["total_booked_revenue"] == 0.0


def test_metrics_counts_outcomes_and_sentiments(client):
    _log(client, "a", outcome="booked", sentiment="positive", final_price=2400.00)
    _log(client, "b", outcome="booked", sentiment="positive", final_price=2350.00)
    _log(client, "c", outcome="carrier_declined", sentiment="negative", load_id=None)
    _log(client, "d", outcome="no_match", sentiment="neutral", load_id=None)

    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["total_calls"] == 4
    assert body["outcomes"]["booked"] == 2
    assert body["outcomes"]["carrier_declined"] == 1
    assert body["outcomes"]["no_match"] == 1
    assert body["sentiment"]["positive"] == 2
    assert body["sentiment"]["negative"] == 1
    assert body["sentiment"]["neutral"] == 1
    # acceptance_rate denominator = booked + carrier_declined + broker_declined = 2+1+0 = 3
    # 2 booked / 3 = 0.666...
    assert abs(body["acceptance_rate"] - (2 / 3)) < 1e-9


def test_metrics_computes_delta_from_loadboard(client):
    # L-9001 loadboard = $2400. Book at $2400 (delta 0) and $2352 (delta -0.02).
    # avg delta = -0.01
    _log(client, "x", outcome="booked", final_price=2400.00)
    _log(client, "y", outcome="booked", final_price=2352.00)

    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["outcomes"]["booked"] == 2
    assert abs(body["avg_delta_from_loadboard"] - (-0.01)) < 1e-9
    assert body["total_booked_revenue"] == 4752.00


def test_metrics_avg_negotiation_rounds(client):
    _log(client, "r1", outcome="booked", negotiation_rounds=1, final_price=2400.00)
    _log(client, "r2", outcome="booked", negotiation_rounds=3, final_price=2400.00)

    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["avg_negotiation_rounds"] == 2.0


def test_metrics_respects_since_filter(client):
    _log(client, "old", outcome="booked", final_price=2400.00, started_at="2020-01-01T00:00:00Z")
    _log(client, "new", outcome="booked", final_price=2400.00, started_at="2026-04-13T14:00:00Z")

    r = client.get("/api/metrics/summary?since=2026-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["total_calls"] == 1
    assert body["outcomes"]["booked"] == 1


def test_metrics_requires_api_key(client):
    r = client.get("/api/metrics/summary")
    assert r.status_code == 401


def test_metrics_rep_hours_and_labor_saved(client):
    # Two booked calls with durations 5:00 and 3:00 = 480 seconds = 0.133 hrs
    # At $45/hr default rate = ~$6.00 saved
    _log(client, "d1", outcome="booked", final_price=2400.00)  # 5 min by default in helper
    _log(client, "d2", outcome="booked", final_price=2400.00)

    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["total_duration_seconds"] == 600  # 2 × 5 min
    assert abs(body["estimated_rep_hours_saved"] - (600 / 3600)) < 1e-9
    assert body["labor_cost_per_hour_usd"] == 45.0
    assert abs(body["estimated_labor_cost_saved_usd"] - (600 / 3600 * 45)) < 1e-9


def test_metrics_recoverable_declines(client):
    # Recoverable: declined + positive/neutral. Not recoverable: declined + negative.
    _log(client, "rec1", outcome="carrier_declined", sentiment="positive", load_id=None)
    _log(client, "rec2", outcome="carrier_declined", sentiment="neutral", load_id=None)
    _log(client, "lost", outcome="carrier_declined", sentiment="negative", load_id=None)
    _log(client, "booked", outcome="booked", sentiment="positive", final_price=2400.00)

    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["recoverable_declines"] == 2


def test_metrics_excludes_error_outcomes_by_default(client):
    """Tab-switch errors must not inflate total_calls or labor savings."""
    _log(client, "ok1", outcome="booked", final_price=2400.00)
    _log(client, "err", outcome="error", load_id=None, sentiment="neutral")

    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["total_calls"] == 1
    assert body["outcomes"]["error"] == 0
    # 1 booked × 5 min = 300s of agent-handled time. Error duration excluded.
    assert body["total_duration_seconds"] == 300


def test_metrics_includes_errors_when_flag_set(client):
    """Diagnostic mode surfaces errors so an operator can chase them."""
    _log(client, "ok", outcome="booked", final_price=2400.00)
    _log(client, "err", outcome="error", load_id=None, sentiment="neutral")

    r = client.get(
        "/api/metrics/summary?since=2020-01-01T00:00:00Z&include_errors=true",
        headers=AUTH,
    )
    body = r.json()
    assert body["total_calls"] == 2
    assert body["outcomes"]["error"] == 1
    # Even with include_errors=true, hours_saved must NOT count the error
    # — an errored call still needed a human, so no time was actually saved.
    assert body["total_duration_seconds"] == 300


def test_metrics_acceptance_by_sentiment(client):
    # Positive: 2 booked, 1 declined → 2/3
    # Neutral: 1 booked → 1/1 = 1.0
    # Negative: 0 booked, 1 declined → 0.0
    _log(client, "p1", outcome="booked", sentiment="positive", final_price=2400.00)
    _log(client, "p2", outcome="booked", sentiment="positive", final_price=2400.00)
    _log(client, "p3", outcome="carrier_declined", sentiment="positive", load_id=None)
    _log(client, "nu1", outcome="booked", sentiment="neutral", final_price=2400.00)
    _log(client, "ng1", outcome="carrier_declined", sentiment="negative", load_id=None)

    r = client.get("/api/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    by_sent = body["acceptance_rate_by_sentiment"]
    assert abs(by_sent["positive"] - (2 / 3)) < 1e-9
    assert by_sent["neutral"] == 1.0
    assert by_sent["negative"] == 0.0
