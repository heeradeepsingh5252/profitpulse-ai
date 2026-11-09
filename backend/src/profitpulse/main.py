import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from profitpulse.db import close_pool
from profitpulse.routers.api import router
from profitpulse.routers.retail import router as retail_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(
    title="ProfitPulse AI API",
    version="1.1.0",
    description="ProfitPulse AI SME analytics, multi-store retail intelligence, RAG and supply-chain workflows.",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Organization-ID", "Accept"],
        max_age=600,
    )

DEMO_READ_ONLY = os.getenv("DEMO_READ_ONLY", "false").lower() in {"1", "true", "yes"}
READ_ONLY_POST_PATHS = {
    "/api/v1/agent/ask",
    "/api/v1/knowledge/search",
}


@app.middleware("http")
async def enforce_demo_read_only(request: Request, call_next):
    if DEMO_READ_ONLY and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        allowed_read_only_post = (
            request.method == "POST" and request.url.path in READ_ONLY_POST_PATHS
        )
        if not allowed_read_only_post:
            return JSONResponse(
                status_code=403,
                content={"detail": "This public portfolio demo is read-only."},
            )
    return await call_next(request)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "profitpulse-api", "version": app.version}


@app.get("/health/db", tags=["health"])
def database_health():
    from profitpulse.db import get_pool

    with get_pool().connection() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "reachable"}


app.include_router(router)
app.include_router(retail_router)
