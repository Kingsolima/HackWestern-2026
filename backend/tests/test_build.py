"""BUILD stage (Omar's before/after viewer): baseline robot first, then every candidate the CAD
worker could model, regenerated bracket highlighted; CAD trouble is reported, never fatal."""

import json

import httpx
import pytest

from app.api.routes import load_demo_robot
from app.cad_client import CadClient
from app.config import Settings
from app.orchestrator.board import MemoryBoard
from app.orchestrator.context import JobContext
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.orchestrator.job import build, run_job
from app.orchestrator.workers import FakeSwapWorker
from app.tfclient.client import TFClient
from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder

pytestmark = pytest.mark.anyio


def fake_cad(requests: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        d = body["design_id"]
        fit = {
            "frame": body["frame"],
            "envelope_used_mm": 66.0,
            "inboard_room_mm": 100.0,
            "fit_envelope": True,
            "ground_clearance_mm": 15.4,
            "fit_ground": True,
            "params": {"min_ground_clearance": 10.0},
            "wheel_bore_mm": 6.35,
            "needs_hub_adapter": False,
        }
        return httpx.Response(
            200,
            json={
                "design_id": d,
                "glb_url": f"/designs/{d}/glb",
                "step_url": f"/designs/{d}/step",
                "fit": fit,
            },
        )

    return httpx.MockTransport(handler)


def context(http: httpx.AsyncClient, tmp_path, cad_url: str = "http://cad") -> JobContext:
    rec = Recorder(Settings().recordings_dir, "replay", replay_speed=0)
    return JobContext(
        job_id="j1",
        mode="replay",
        robot=load_demo_robot(),
        log=EventLog("j1"),
        tf=TFClient(rec, http, ""),
        fleet=Fleet({"agent": 1, "browser": 1, "search": 1, "fetch": 1, "gemini": 1}),
        budget=JobBudget(),
        board=MemoryBoard(),
        cad=CadClient(http, cad_url),
        gemini=GeminiClient(rec, http, "", "flash"),
    )


async def test_build_emits_baseline_then_candidate(tmp_path):
    sent: list[dict] = []
    async with httpx.AsyncClient(transport=fake_cad(sent)) as http:
        ctx = context(http, tmp_path)
        final = await run_job(ctx, [FakeSwapWorker()])
    assert final == "DONE", [e.data for e in ctx.log.events if e.type == "error"]

    ready = [e.data for e in ctx.log.events if e.type == "design_ready"]
    assert [r["role"] for r in ready] == ["baseline", "candidate"]
    assert [r["frame"] for r in ready] == ["23", "23"]
    assert ready[1]["glb_url"] == f"/designs/{ready[1]['design_id']}/glb"
    assert ready[1]["fit"]["ground_clearance_mm"] == 15.4
    assert ready[0]["candidate_id"] is None and ready[1]["candidate_id"]
    # only the regenerated bracket is highlighted; both use the CAD worker's wheel bore
    by_id = {r["design_id"]: r for r in sent}
    assert by_id[ready[0]["design_id"]]["highlight"] is False
    assert by_id[ready[1]["design_id"]]["highlight"] is True
    assert not any("wheel_bore" in r for r in sent)


async def test_cad_down_is_reported_and_the_job_still_finishes(tmp_path):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as http:
        ctx = context(http, tmp_path)
        final = await run_job(ctx, [FakeSwapWorker()])

    errors = [e.data for e in ctx.log.events if e.type == "error"]
    assert final == "DONE"
    assert errors and errors[-1]["stage"] == "BUILD" and "unreachable" in errors[-1]["message"]
    assert not [e for e in ctx.log.events if e.type == "design_ready"]


async def test_no_cad_worker_configured_is_reported(tmp_path):
    async with httpx.AsyncClient() as http:
        ctx = context(http, tmp_path, cad_url="")
        await build(ctx, [])
    assert [e.data["message"] for e in ctx.log.events] == [
        "no CAD worker configured (CAD_WORKER_URL)"
    ]


async def test_a_fit_without_the_checked_numbers_is_reported_not_fatal(tmp_path):
    def partial(request: httpx.Request) -> httpx.Response:
        d = json.loads(request.content)["design_id"]
        body = {"design_id": d, "glb_url": "g", "step_url": "s", "fit": {"fit_ground": True}}
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(partial)) as http:
        ctx = context(http, tmp_path)
        final = await run_job(ctx, [FakeSwapWorker()])
    assert final == "DONE"
    errors = [e.data for e in ctx.log.events if e.type == "error"]
    assert errors[0]["stage"] == "CHECK" and "returned no envelope_used_mm" in errors[0]["message"]
    fits = [e.data["check"] for e in ctx.log.events if e.type == "check_result"]
    assert {f["verdict"] for f in fits if f["check"].startswith("fit")} == {"review"}
