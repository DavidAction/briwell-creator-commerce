import asyncio
from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.rate_limit import SlidingWindowRateLimiter, client_identity
from app.workers.job_handlers import JOB_HANDLERS
from app.workers.job_queue import run_loop


logger = logging.getLogger("briwell")
from app.routers import (
    analysis_jobs,
    ai,
    ai_invocation_logs,
    campaigns,
    comments,
    commerce,
    compliance,
    creators,
    discovery,
    health,
    keywords,
    ops,
    operations,
    outreach,
    performance,
    portal,
    products,
    providers,
    settlements,
    shopify_webhooks,
    trends,
    videos,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    outbox_worker_task = None
    if settings.use_database and settings.outbox_worker_enabled:
        outbox_worker_task = asyncio.create_task(
            run_loop(JOB_HANDLERS, settings.outbox_worker_poll_interval_seconds)
        )
    try:
        yield
    finally:
        if outbox_worker_task is not None:
            outbox_worker_task.cancel()


app = FastAPI(
    title="Briwell Influencer Intelligence API",
    version="0.1.0",
    description="MVP backend scaffold for Low/Medium Risk influencer discovery.",
    lifespan=lifespan,
)

if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        # DELETE covers the portal-token kill switch (DELETE /portal/tokens/{creator_id});
        # without it the browser preflight fails and the dashboard cannot revoke links.
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-User-Email",
            "X-User-Role",
        ],
    )


@app.middleware("http")
async def add_request_context_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Single-process, in-memory limiter -- intentional scope decision for this internal tool,
# not backed by Redis/slowapi. See app/core/rate_limit.py.
rate_limiter = SlidingWindowRateLimiter(
    requests_per_minute=settings.rate_limit_requests_per_minute,
    burst=settings.rate_limit_burst,
)


@app.middleware("http")
async def enforce_rate_limit(request: Request, call_next):
    if not settings.rate_limit_enabled or request.url.path == "/health":
        return await call_next(request)

    # X-User-Email is a client-supplied header, not a server-verified identity (the auth
    # dependency that verifies it, incl. OIDC, runs later at the route level) -- keying the
    # limiter on it would let a caller bypass its own limit by rotating the header value.
    client_host = request.client.host if request.client else None
    client_key = client_identity(None, client_host)
    result = await rate_limiter.check(client_key)
    if not result.allowed:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response = JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Slow down and retry later.",
                    "request_id": request_id,
                }
            },
        )
        response.headers["Retry-After"] = str(result.retry_after_seconds)
        response.headers["X-Request-ID"] = request_id
        return response
    return await call_next(request)


# Flags read by the readiness endpoint so /ops/readiness reflects what is actually
# installed instead of hardcoded True. Set next to the install so removing one removes both.
app.state.request_id_middleware_enabled = True
app.state.security_headers_enabled = True
app.state.rate_limit_middleware_enabled = True
app.state.outbox_worker_enabled = settings.use_database and settings.outbox_worker_enabled


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Return a clean JSON error for any unhandled exception so internal stack traces are
    never leaked in responses. The full traceback is logged server-side with the request id.
    HTTPException and validation errors keep FastAPI's own handlers (this only catches the
    truly unexpected)."""
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    logger.exception(
        "Unhandled error [request_id=%s] %s %s", request_id, request.method, request.url.path
    )
    response = JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Contact an operator with the request id.",
                "request_id": request_id,
            }
        },
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.state.global_exception_handler_enabled = True


app.include_router(health.router)
app.include_router(creators.router)
app.include_router(discovery.router)
app.include_router(keywords.router)
app.include_router(videos.router)
app.include_router(comments.router)
app.include_router(compliance.router)
app.include_router(ai.router)
app.include_router(analysis_jobs.router)
app.include_router(ai_invocation_logs.router)
app.include_router(campaigns.router)
app.include_router(outreach.router)
app.include_router(performance.router)
app.include_router(products.router)
app.include_router(providers.router)
app.include_router(settlements.router)
app.include_router(portal.router)
app.include_router(commerce.router)
app.include_router(shopify_webhooks.router)
app.include_router(trends.router)
app.include_router(ops.router)
app.include_router(operations.router)
