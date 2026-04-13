"""In-memory sliding-window rate limiter.

Per-IP, per-process. Not suitable for multi-replica production — this is the
PoC limiter described in docs/SECURITY.md. For prod we'd swap for Redis or an
ALB/WAF rule. No state purge runs in the background; buckets that stop being
hit stay in memory. For an exposed PoC on Fargate the blast radius is bounded.
"""
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class InMemoryRateLimiter(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        limit: int = 60,
        window_seconds: int = 60,
        exempt_paths: tuple[str, ...] = ("/health",),
    ) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window_seconds
        self.exempt = set(exempt_paths)
        self.buckets: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exempt:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = self.buckets[client_ip]

        cutoff = now - self.window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": f"limit {self.limit} requests per {self.window}s per IP",
                        "request_id": request.headers.get("X-Request-ID", "-"),
                    }
                },
            )

        bucket.append(now)
        return await call_next(request)
