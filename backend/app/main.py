import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.designs import router as designs_router
from app.api.intake import router as intake_router
from app.api.jobs import projects_router
from app.api.jobs import router as jobs_router
from app.api.routes import router
from app.api.runs import router as runs_router
from app.api.sites import router as sites_router
from app.config import settings
from app.db.tiger import TigerDB, connect
from app.orchestrator.runtime import Runtime


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db = TigerDB(settings.database_url) if settings.tiger_enabled else None
    if db is not None:
        await db.open()
        await db.apply_schema()
    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            app.state.runtime = Runtime(settings, http, db)
            yield
    finally:
        if db is not None:
            await db.close()


app = FastAPI(title="AI Robot Redesign Engine", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(jobs_router)
app.include_router(projects_router)
app.include_router(designs_router)
app.include_router(intake_router)
app.include_router(sites_router)
app.include_router(runs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> JSONResponse:
    """Can the backend reach the database at DATABASE_URL? Separate from /health, so a database
    outage never reads as the site being down. `board` says where facts are kept."""
    board = "tiger" if settings.tiger_enabled else "memory"
    try:
        async with asyncio.timeout(8):
            async with connect() as conn:
                await conn.execute("SELECT 1")
    except Exception as exc:  # any failure is the answer; never the password-bearing message
        body = {"status": "error", "error": type(exc).__name__, "board": board}
        return JSONResponse(body, status_code=503)
    return JSONResponse({"status": "ok", "board": board})
