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
    return client.post("/log-call", json=payload, headers=AUTH)


def test_metrics_empty(client):
    r = client.get("/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
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

    r = client.get("/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["total_calls"] == 4
    assert body["outcomes"]["booked"] == 2
    assert body["outcomes"]["carrier_declined"] == 1
    assert body["outcomes"]["no_match"] == 1
    assert body["sentiment"]["positive"] == 2
    assert body["sentiment"]["negative"] == 1
    assert body["sentiment"]["neutral"] == 1
    assert body["acceptance_rate"] == 0.5  # 2 booked / 4 total


def test_metrics_computes_delta_from_loadboard(client):
    # L-9001 loadboard = $2400. Book at $2400 (delta 0) and $2352 (delta -0.02).
    # avg delta = -0.01
    _log(client, "x", outcome="booked", final_price=2400.00)
    _log(client, "y", outcome="booked", final_price=2352.00)

    r = client.get("/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["outcomes"]["booked"] == 2
    assert abs(body["avg_delta_from_loadboard"] - (-0.01)) < 1e-9
    assert body["total_booked_revenue"] == 4752.00


def test_metrics_avg_negotiation_rounds(client):
    _log(client, "r1", outcome="booked", negotiation_rounds=1, final_price=2400.00)
    _log(client, "r2", outcome="booked", negotiation_rounds=3, final_price=2400.00)

    r = client.get("/metrics/summary?since=2020-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["avg_negotiation_rounds"] == 2.0


def test_metrics_respects_since_filter(client):
    _log(client, "old", outcome="booked", final_price=2400.00, started_at="2020-01-01T00:00:00Z")
    _log(client, "new", outcome="booked", final_price=2400.00, started_at="2026-04-13T14:00:00Z")

    r = client.get("/metrics/summary?since=2026-01-01T00:00:00Z", headers=AUTH)
    body = r.json()
    assert body["total_calls"] == 1
    assert body["outcomes"]["booked"] == 1


def test_metrics_requires_api_key(client):
    r = client.get("/metrics/summary")
    assert r.status_code == 401
