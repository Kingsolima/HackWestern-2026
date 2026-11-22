from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.designs import router as designs_router
from app.api.intake import router as intake_router
from app.api.jobs import projects_router
from app.api.jobs import router as jobs_router
from app.api.routes import router
from app.api.sites import router as sites_router
from app.config import settings
from app.db.tiger import TigerDB
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
app.include_router(sites_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
