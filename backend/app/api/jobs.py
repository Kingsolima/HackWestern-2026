"""Job API: start a redesign job and stream its events (docs/design/04 section 8)."""

import secrets
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from app.api.routes import load_demo_robot
from app.intake.schema import CompanyFact
from app.intake.to_project import project_from_onboarding
from app.orchestrator.events import Stage
from app.orchestrator.job import Job
from app.orchestrator.runtime import Runtime
from app.projects import UnknownProject, list_projects, load_project
from app.schemas import JobMode, Robot

router = APIRouter(prefix="/api/jobs")


class JobRequest(BaseModel):
    robot: Robot | None = None
    mode: JobMode = "replay"
    project_id: str | None = None  # data/projects/<id>.json; None = the v3 wheeled demo job
    # The company facts confirmed in onboarding. With `robot` (its numbers and BOM) they make a
    # project, so the job runs the risk map and recommendations. Ignored when project_id is set.
    company: list[CompanyFact] | None = None


class ProjectSummary(BaseModel):
    id: str
    kind: str
    name: str
    robot: str
    use_case: str


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


def require_live_permission(mode: JobMode, token: str | None, runtime: Runtime) -> None:
    """Live and mixed jobs spend TinyFish credit; on a public deploy they need the token."""
    settings = runtime.settings
    if mode == "replay" or not settings.require_live_token:
        return
    expected = settings.live_jobs_token
    if not expected or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="live jobs need a valid X-Live-Token")


@router.post("", status_code=201)
async def create_job(
    body: JobRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
    x_live_token: Annotated[str | None, Header()] = None,
) -> JobStatus:
    require_live_permission(body.mode, x_live_token, runtime)
    project = None
    if body.project_id is not None:
        try:
            project = load_project(body.project_id)
        except UnknownProject:
            raise HTTPException(status_code=404, detail=f"no project {body.project_id}") from None
    robot = body.robot or load_demo_robot()
    if project is None and body.company is not None:
        project = project_from_onboarding(body.company, robot)
    return status(runtime.start_job(robot, body.mode, project))


projects_router = APIRouter(prefix="/api/projects")


@projects_router.get("")
def get_projects() -> list[ProjectSummary]:
    return [ProjectSummary.model_validate(p, from_attributes=True) for p in list_projects()]


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
