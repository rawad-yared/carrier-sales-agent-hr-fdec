from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import InMemoryRateLimiter


def _app(limit: int, exempt_paths=("/health",)) -> FastAPI:
    """Fresh throwaway app with an isolated rate limiter instance."""
    app = FastAPI()
    app.add_middleware(InMemoryRateLimiter, limit=limit, exempt_paths=exempt_paths)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_rate_limiter_blocks_after_limit():
    client = TestClient(_app(limit=3))
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    r = client.get("/ping")
    assert r.status_code == 429
    body = r.json()
    assert body["error"]["code"] == "rate_limit_exceeded"


def test_rate_limiter_exempts_health():
    client = TestClient(_app(limit=2))
    # /health doesn't count against the bucket
    for _ in range(10):
        assert client.get("/health").status_code == 200
    # /ping still has a full bucket
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429


def test_rate_limiter_isolated_per_instance():
    # Two apps should not share state
    c1 = TestClient(_app(limit=1))
    c2 = TestClient(_app(limit=1))
    assert c1.get("/ping").status_code == 200
    assert c2.get("/ping").status_code == 200
    assert c1.get("/ping").status_code == 429
    assert c2.get("/ping").status_code == 429
