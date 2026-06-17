from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    analysis_jobs,
    ai,
    ai_invocation_logs,
    campaigns,
    comments,
    compliance,
    creators,
    discovery,
    health,
    keywords,
    ops,
    operations,
    outreach,
    performance,
    products,
    settlements,
    videos,
)


app = FastAPI(
    title="Briwell Influencer Intelligence API",
    version="0.1.0",
    description="MVP backend scaffold for Low/Medium Risk influencer discovery.",
)

if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
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
app.include_router(settlements.router)
app.include_router(ops.router)
app.include_router(operations.router)
