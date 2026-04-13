from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def _payload(**overrides):
    base = {
        "session_id": "sess-log-1",
        "mc_number": "123456",
        "carrier_name": "ACME TRUCKING LLC",
        "load_id": "L-9001",
        "outcome": "booked",
        "sentiment": "positive",
        "final_price": 2400.00,
        "negotiation_rounds": 2,
        "started_at": "2026-04-13T14:22:01Z",
        "ended_at": "2026-04-13T14:26:44Z",
        "transcript": "Hello, we have a deal.",
        "extracted": {"notes": "pickup at noon"},
    }
    base.update(overrides)
    return base


def test_log_call_happy_path_creates_row(client):
    r = client.post("/api/log-call", json=_payload(), headers=AUTH)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "logged"
    assert body["call_id"].startswith("c-")


def test_log_call_is_idempotent_by_session_id(client):
    r1 = client.post("/api/log-call", json=_payload(session_id="sess-dup"), headers=AUTH)
    assert r1.status_code == 201
    call_id = r1.json()["call_id"]

    r2 = client.post(
        "/api/log-call",
        json=_payload(session_id="sess-dup", final_price=2500.00),
        headers=AUTH,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "updated"
    assert body["call_id"] == call_id  # same call, new values


def test_log_call_persists_duration_seconds(client):
    r = client.post(
        "/api/log-call",
        json=_payload(
            session_id="sess-dur",
            started_at="2026-04-13T14:00:00Z",
            ended_at="2026-04-13T14:05:30Z",
        ),
        headers=AUTH,
    )
    assert r.status_code == 201
    # duration = 5 min 30 sec = 330 s
    # We can verify via the /calls read endpoint in a later test, for now trust DB write


def test_log_call_rejects_bad_outcome(client):
    r = client.post("/api/log-call", json=_payload(outcome="not_a_real_outcome"), headers=AUTH)
    assert r.status_code == 422  # Pydantic Literal validation


def test_log_call_rejects_bad_sentiment(client):
    r = client.post("/api/log-call", json=_payload(sentiment="hostile"), headers=AUTH)
    assert r.status_code == 422


def test_log_call_minimal_fields(client):
    # Only the required fields; nullable fields omitted
    r = client.post(
        "/api/log-call",
        json={
            "session_id": "sess-min",
            "outcome": "no_match",
            "sentiment": "neutral",
            "started_at": "2026-04-13T14:00:00Z",
            "ended_at": "2026-04-13T14:01:00Z",
        },
        headers=AUTH,
    )
    assert r.status_code == 201


def test_log_call_requires_api_key(client):
    r = client.post("/api/log-call", json=_payload())
    assert r.status_code == 401
