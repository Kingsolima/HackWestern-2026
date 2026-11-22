import asyncio

import httpx
import pytest

from app.api.routes import load_demo_robot
from app.cad_client import CadClient
from app.orchestrator.board import MemoryBoard
from app.orchestrator.context import JobContext
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.orchestrator.job import run_job
from app.tfclient.client import TFClient
from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder

pytestmark = pytest.mark.anyio


class SleepyWorker:
    name = "swap:sleepy"

    async def run(self, ctx):
        await asyncio.sleep(3600)
        return []


async def test_cancelled_job_still_ends_failed_and_closes_its_log(tmp_path):
    async with httpx.AsyncClient() as http:
        ctx = JobContext(
            job_id="j1",
            mode="replay",
            robot=load_demo_robot(),
            log=EventLog("j1"),
            tf=TFClient(Recorder(tmp_path, "replay"), http, api_key=""),
            fleet=Fleet({"fetch": 1}),
            budget=JobBudget(),
            board=MemoryBoard(),
            cad=CadClient(http, "http://cad.invalid"),
            gemini=GeminiClient(Recorder(tmp_path, "replay"), http, "", "flash"),
        )
        task = asyncio.create_task(run_job(ctx, [SleepyWorker()]))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert ctx.log.closed
    assert ctx.log.events[-1].data == {"stage": "FAILED"}
