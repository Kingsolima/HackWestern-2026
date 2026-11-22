"""Success by site (docs/design/07 section 3): how TinyFish and Gemini calls fare per site."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.jobs import get_runtime
from app.db.tiger import SiteSuccess
from app.orchestrator.run_log import site_success_from
from app.orchestrator.runtime import Runtime

router = APIRouter(prefix="/api/sites")


class SitesSuccess(BaseModel):
    source: Literal["tiger", "memory"]  # tiger: last 24 h, every job ever; memory: this process
    sites: list[SiteSuccess]


@router.get("/success")
async def get_site_success(runtime: Annotated[Runtime, Depends(get_runtime)]) -> SitesSuccess:
    if runtime.db is not None:
        return SitesSuccess(source="tiger", sites=await runtime.db.site_success())
    logs = [job.ctx.log for job in runtime.jobs.values()]
    return SitesSuccess(source="memory", sites=site_success_from(logs))
