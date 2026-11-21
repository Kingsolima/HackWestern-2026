"""Job API: start a redesign job and stream its events (docs/design/04 section 8)."""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from app.api.routes import load_demo_robot
from app.orchestrator.events import Stage
from app.orchestrator.job import Job
from app.orchestrator.runtime import Runtime
from app.schemas import JobMode, Robot

router = APIRouter(prefix="/api/jobs")


class JobRequest(BaseModel):
    robot: Robot | None = None
    mode: JobMode = "replay"


class JobStatus(BaseModel):
    job_id: str
    mode: JobMode
    stage: Stage
    created_at: datetime
    events: int


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def get_job(job_id: str, runtime: Annotated[Runtime, Depends(get_runtime)]) -> Job:
    job = runtime.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"no job {job_id}")
    return job


def status(job: Job) -> JobStatus:
    return JobStatus(
        job_id=job.ctx.job_id,
        mode=job.ctx.mode,
        stage=job.stage,
        created_at=job.created_at,
        events=len(job.ctx.log.events),
    )


@router.post("", status_code=201)
async def create_job(
    body: JobRequest, runtime: Annotated[Runtime, Depends(get_runtime)]
) -> JobStatus:
    return status(runtime.start_job(body.robot or load_demo_robot(), body.mode))


@router.get("/{job_id}")
def get_job_status(job: Annotated[Job, Depends(get_job)]) -> JobStatus:
    return status(job)


@router.get("/{job_id}/events", response_class=EventSourceResponse)
async def job_events(
    job: Annotated[Job, Depends(get_job)],
    last_event_id: Annotated[int, Header()] = 0,
) -> AsyncIterator[ServerSentEvent]:
    """Replays the log after Last-Event-ID, then follows it until the job ends."""
    async for event in job.ctx.log.subscribe(last_event_id):
        yield ServerSentEvent(data=event.model_dump(mode="json"), id=str(event.id))
