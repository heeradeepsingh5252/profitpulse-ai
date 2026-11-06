from contextlib import asynccontextmanager

from fastapi import FastAPI

from profitpulse.db import close_pool
from profitpulse.routers.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(
    title="ProfitPulse AI API",
    version="1.0.0",
    description="Demo API for ProfitPulse AI SME business analytics, financial intelligence, RAG and supply-chain workflows.",
    lifespan=lifespan,
)


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
