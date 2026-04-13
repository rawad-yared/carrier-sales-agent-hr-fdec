def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_requires_no_auth(client):
    r = client.get("/health")  # no X-API-Key header
    assert r.status_code == 200
