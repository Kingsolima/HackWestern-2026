"""BUILD stage: asks the CAD worker for the before/after robots and emits design_ready."""

import json

import httpx
import pytest

from app.api.routes import load_demo_robot
from app.orchestrator.board import MemoryBoard
from app.orchestrator.cad import CadClient
from app.orchestrator.context import JobContext
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.orchestrator.job import build, run_job
from app.tfclient.client import TFClient
from app.tfclient.recorder import Recorder

pytestmark = pytest.mark.anyio


def fake_cad(requests: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        d = body["design_id"]
        return httpx.Response(
            200,
            json={
                "design_id": d,
                "glb_url": f"/designs/{d}/glb",
                "step_url": f"/designs/{d}/step",
                "fit": {"frame": body["frame"], "ground_clearance_mm": 15.4},
            },
        )

    return httpx.MockTransport(handler)


def context(http: httpx.AsyncClient, tmp_path, cad: CadClient | None) -> JobContext:
    return JobContext(
        job_id="j1",
        mode="replay",
        robot=load_demo_robot(),
        log=EventLog("j1"),
        tf=TFClient(Recorder(tmp_path, "replay"), http, ""),
        fleet=Fleet({"agent": 1, "browser": 1, "search": 1, "fetch": 1, "gemini": 1}),
        budget=JobBudget(),
        board=MemoryBoard(),
        cad=cad,
    )


async def test_build_emits_baseline_then_candidate(tmp_path):
    sent: list[dict] = []
    async with httpx.AsyncClient(transport=fake_cad(sent)) as http:
        ctx = context(http, tmp_path, CadClient("http://cad", http))
        await build(ctx, [])

    ready = [e for e in ctx.log.events if e.type == "design_ready"]
    assert [e.data["role"] for e in ready] == ["baseline", "candidate"]
    assert [e.data["frame"] for e in ready] == ["17", "23"]
    assert ready[1].data["glb_url"] == "/designs/j1-after/glb"
    assert ready[1].data["fit"]["ground_clearance_mm"] == 15.4
    # only the regenerated design is highlighted; both share the baseline wheel bore
    assert [r.get("highlight", False) for r in sent] == [False, True]
    assert sent[0]["wheel_bore"] == sent[1]["wheel_bore"] == 5.0


async def test_cad_down_is_reported_and_the_job_still_finishes(tmp_path):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as http:
        ctx = context(http, tmp_path, CadClient("http://cad", http))
        final = await run_job(ctx, [])

    errors = [e.data for e in ctx.log.events if e.type == "error"]
    assert final == "DONE"
    assert errors and errors[0]["stage"] == "BUILD" and "unreachable" in errors[0]["message"]
    assert not [e for e in ctx.log.events if e.type == "design_ready"]


async def test_no_cad_client_is_reported(tmp_path):
    async with httpx.AsyncClient() as http:
        ctx = context(http, tmp_path, None)
        await build(ctx, [])
    assert [e.data["message"] for e in ctx.log.events] == ["no CAD worker configured"]
