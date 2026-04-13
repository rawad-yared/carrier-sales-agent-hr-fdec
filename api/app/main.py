import logging
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("carrier_sales_api")
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = _request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response


def current_request_id() -> str:
    return _request_id_ctx.get()


from app.config import get_settings  # noqa: E402
from app.middleware.rate_limit import InMemoryRateLimiter  # noqa: E402

app = FastAPI(title="Carrier Sales API", version="0.1.0")
# Order matters: add_middleware is LIFO on request. Adding RateLimiter first
# then RequestId means RequestId wraps RateLimiter — so even 429 responses
# carry a request_id set by the outer middleware.
app.add_middleware(InMemoryRateLimiter, limit=get_settings().rate_limit_per_min)
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code = detail.get("code", "http_error")
        message = detail.get("message", "")
    else:
        code = "http_error"
        message = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "request_id": current_request_id()}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled exception", extra={"request_id": current_request_id()})
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "an unexpected error occurred",
                "request_id": current_request_id(),
            }
        },
    )


from app.routers import calls, carriers, health, loads, metrics, offers  # noqa: E402

# /health is mounted at the root for ALB target-group health checks that hit the
# task directly on port 8000 (the ALB bypasses path routing for health).
# All application routers are mounted under /api for ALB path-based routing:
# ALB rule `/api/*` → api target group, default → dashboard target group.
app.include_router(health.router)
app.include_router(health.router, prefix="/api")
app.include_router(loads.router, prefix="/api")
app.include_router(offers.router, prefix="/api")
app.include_router(carriers.router, prefix="/api")
app.include_router(calls.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
