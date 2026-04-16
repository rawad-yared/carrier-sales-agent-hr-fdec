from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def _log(client, session_id, outcome="booked", sentiment="positive", started_at="2026-04-13T14:00:00Z"):
    return client.post(
        "/api/log-call",
        json={
            "session_id": session_id,
            "outcome": outcome,
            "sentiment": sentiment,
            "started_at": started_at,
            "ended_at": "2026-04-13T14:05:00Z",
        },
        headers=AUTH,
    )


def test_list_calls_empty(client):
    r = client.get("/api/calls", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["results"] == []
    assert body["limit"] == 50
    assert body["offset"] == 0


def test_list_calls_returns_all_logged(client):
    _log(client, "s1")
    _log(client, "s2", outcome="no_match", sentiment="neutral")
    _log(client, "s3", outcome="carrier_declined", sentiment="negative")

    r = client.get("/api/calls", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["results"]) == 3


def test_list_calls_filters_by_outcome(client):
    _log(client, "b1", outcome="booked")
    _log(client, "b2", outcome="booked")
    _log(client, "n1", outcome="no_match", sentiment="neutral")

    r = client.get("/api/calls?outcome=booked", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_list_calls_filters_by_since(client):
    _log(client, "old", started_at="2026-04-10T14:00:00Z")
    _log(client, "new", started_at="2026-04-12T14:00:00Z")

    r = client.get("/api/calls?since=2026-04-11T00:00:00Z", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["session_id"] == "new"


def test_list_calls_pagination(client):
    for i in range(5):
        _log(client, f"p{i}", started_at=f"2026-04-13T14:{i:02d}:00Z")

    r = client.get("/api/calls?limit=2&offset=0", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["results"]) == 2

    r2 = client.get("/api/calls?limit=2&offset=2", headers=AUTH)
    assert r2.status_code == 200
    assert len(r2.json()["results"]) == 2


def test_list_calls_orders_by_started_at_desc(client):
    _log(client, "first", started_at="2026-04-13T10:00:00Z")
    _log(client, "second", started_at="2026-04-13T12:00:00Z")
    _log(client, "third", started_at="2026-04-13T14:00:00Z")

    r = client.get("/api/calls", headers=AUTH)
    ids = [row["session_id"] for row in r.json()["results"]]
    assert ids == ["third", "second", "first"]


def test_list_calls_requires_api_key(client):
    r = client.get("/api/calls")
    assert r.status_code == 401


def test_list_calls_excludes_error_outcome_by_default(client):
    """Tab-switch errors from HappyRobot must not pollute the demo feed."""
    _log(client, "ok1", outcome="booked")
    _log(client, "ok2", outcome="no_match", sentiment="neutral")
    _log(client, "err", outcome="error", sentiment="neutral")

    r = client.get("/api/calls", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {row["session_id"] for row in body["results"]} == {"ok1", "ok2"}


def test_list_calls_includes_error_when_flag_set(client):
    _log(client, "ok", outcome="booked")
    _log(client, "err", outcome="error", sentiment="neutral")

    r = client.get("/api/calls?include_errors=true", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_list_calls_explicit_error_filter_still_works(client):
    """Operators must still be able to inspect errors directly."""
    _log(client, "ok", outcome="booked")
    _log(client, "err", outcome="error", sentiment="neutral")

    r = client.get("/api/calls?outcome=error", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["session_id"] == "err"
