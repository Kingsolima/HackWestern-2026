"""Process-wide pieces jobs share: one HTTP client, the account's fleet slots and the board."""

import asyncio
import uuid

import httpx

from app.cad_client import CadClient
from app.config import Settings
from app.orchestrator.board import MemoryBoard
from app.orchestrator.context import JobContext
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.orchestrator.job import Job, run_job
from app.orchestrator.workers import SwapWorker, Worker
from app.schemas import JobMode, Robot
from app.tfclient.client import TFClient
from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder


class Runtime:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http = http
        self.fleet = Fleet(
            {
                "agent": settings.agent_slots,
                "browser": settings.browser_slots,
                "search": settings.search_slots,
                "fetch": settings.fetch_slots,
                "gemini": settings.gemini_slots,
            }
        )
        self.board = MemoryBoard()
        self.cad = CadClient(http, settings.cad_worker_url)
        self.jobs: dict[str, Job] = {}

    def workers(self, mode: JobMode) -> list[Worker]:
        return [SwapWorker()]

    def gemini(self, mode: JobMode) -> GeminiClient:
        """A Gemini client outside a job (the intake API)."""
        recorder = Recorder(self.settings.recordings_dir, mode, self.settings.replay_speed)
        return GeminiClient(
            recorder, self.http, self.settings.gemini_api_key, self.settings.gemini_flash_model
        )

    def start_job(self, robot: Robot, mode: JobMode) -> Job:
        job_id = uuid.uuid4().hex[:12]
        recorder = Recorder(self.settings.recordings_dir, mode, self.settings.replay_speed)
        ctx = JobContext(
            job_id=job_id,
            mode=mode,
            robot=robot,
            log=EventLog(job_id),
            tf=TFClient(recorder, self.http, self.settings.tinyfish_api_key),
            fleet=self.fleet,
            budget=JobBudget(max_agent_runs=self.settings.max_agent_runs_per_job),
            board=self.board,
            cad=self.cad,
            gemini=GeminiClient(
                recorder, self.http, self.settings.gemini_api_key, self.settings.gemini_flash_model
            ),
        )
        job = Job(ctx=ctx)
        job.task = asyncio.create_task(run_job(ctx, self.workers(mode)))
        self.jobs[job_id] = job
        return job
