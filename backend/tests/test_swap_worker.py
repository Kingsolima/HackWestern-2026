import json
from pathlib import Path

import httpx
import pytest

from app.agents.targets import MOTOR_SCHEMA, TEKNIC, SwapTarget
from app.api.routes import load_demo_robot
from app.cad_client import CadClient
from app.orchestrator.board import MemoryBoard
from app.orchestrator.context import JobContext
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.orchestrator.workers import SwapWorker, claims_from_candidate
from app.schemas import AgentMotorCandidate
from app.tfclient.client import AGENT_SSE_URL, RUNS_URL, TFClient
from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder

pytestmark = pytest.mark.anyio

REPO = Path(__file__).resolve().parents[2]
REAL_RUN = json.loads((Path(__file__).parent / "fixtures/teknic/agent_run.json").read_text())
REAL_RESULT = REAL_RUN["events"][-1]["result"]


def test_packaged_schema_is_the_contract():
    contract = REPO / "docs/design/schemas/motor_candidate.tinyfish.json"
    assert MOTOR_SCHEMA == json.loads(contract.read_text())


def test_omars_live_run_used_the_contract_schema():
    assert REAL_RUN["request"]["output_schema"] == MOTOR_SCHEMA


def test_claims_from_the_real_teknic_result():
    claims = claims_from_candidate(AgentMotorCandidate.model_validate(REAL_RESULT), "r1", True)
    assert len(claims) == 9
    by_field = {c.field: c for c in claims}
    assert by_field["max_speed"].raw_value == "4000.0"
    assert by_field["shaft_diameter"].raw_value == "0.375"
    origin = by_field["country_of_origin"]
    assert (origin.raw_value, origin.source.url) == ("USA", "https://teknic.com/about/")
    assert {c.candidate_id for c in claims} == {"CPM-SDSK-2310D-RLN"}
    assert {c.source.via for c in claims} == {"tinyagent"}


def test_huge_values_stay_plain_decimals():
    result = REAL_RESULT | {
        "specs": [REAL_RESULT["specs"][0] | {"value": 1e16}],
        "origin_quote": None,
    }
    [claim] = claims_from_candidate(AgentMotorCandidate.model_validate(result), "r1", False)
    assert claim.raw_value == "10000000000000000"
    assert claim.source.via == "replay"


def test_pdf_sources_are_marked_pdf():
    spec = REAL_RESULT["specs"][0] | {"source_url": "https://x/manual.PDF"}
    result = REAL_RESULT | {"specs": [spec], "origin_quote": None}
    [claim] = claims_from_candidate(AgentMotorCandidate.model_validate(result), "r1", True)
    assert claim.source.kind == "pdf"


def sse(*events) -> str:
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events)


def complete(status_in_result="success", tf_status="COMPLETED"):
    return {
        "type": "COMPLETE",
        "run_id": "r1",
        "status": tf_status,
        "result": REAL_RESULT | {"status": status_in_result},
        "timestamp": "2026-11-21T20:01:00+00:00",
    }


STARTED = {"type": "STARTED", "run_id": "r1", "timestamp": "2026-11-21T20:00:00+00:00"}
STREAM = {"type": "STREAMING_URL", "run_id": "r1", "streaming_url": "https://s/0"}
PROGRESS = {"type": "PROGRESS", "run_id": "r1", "purpose": "Open model page"}


def context(tmp_path, handler) -> tuple[JobContext, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(record))
    ctx = JobContext(
        job_id="j1",
        mode="live",
        robot=load_demo_robot(),
        log=EventLog("j1"),
        tf=TFClient(Recorder(tmp_path, "live"), http, api_key="k", poll_s=0),
        fleet=Fleet({"agent": 2}),
        budget=JobBudget(),
        board=MemoryBoard(),
        cad=CadClient(http, "http://cad.invalid"),
        gemini=GeminiClient(Recorder(tmp_path, "replay"), http, "", "flash"),
    )
    return ctx, seen


def sse_response(body: str) -> httpx.Response:
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


async def test_successful_run_emits_tile_events_and_returns_claims(tmp_path):
    ctx, seen = context(
        tmp_path, lambda r: sse_response(sse(STARTED, STREAM, PROGRESS, complete()))
    )
    [candidate] = await SwapWorker().run(ctx)
    assert len(candidate.claims) == 9
    assert (candidate.id, candidate.motor_type, candidate.nema_frame) == (
        "CPM-SDSK-2310D-RLN",
        "servo_integrated",
        "23",
    )
    assert candidate.product_url == "https://teknic.com/model-info/CPM-SDSK-2310D-RLN/"
    types = [e.type for e in ctx.log.events]
    assert types == ["run_started", "run_streaming_url", "run_progress", "run_finished"]
    finished = ctx.log.events[-1].data
    assert (finished["outcome"], finished["live"], finished["duration_s"]) == ("success", True, 60)
    assert json.loads(seen[0].content)["url"] == TEKNIC.url


async def test_blocked_run_is_retried_once_with_stealth_and_us_proxy(tmp_path):
    def handler(request):
        stealth = json.loads(request.content)["browser_profile"] == "stealth"
        return sse_response(sse(STARTED, complete("success" if stealth else "blocked")))

    ctx, seen = context(tmp_path, handler)
    [candidate] = await SwapWorker().run(ctx)
    assert len(candidate.claims) == 9
    bodies = [json.loads(r.content) for r in seen]
    assert [b["browser_profile"] for b in bodies] == ["lite", "stealth"]
    assert bodies[1]["proxy_config"] == {"enabled": True, "country_code": "US"}
    assert ctx.budget.agent_runs == 2


async def test_not_found_is_not_retried_and_yields_no_claims(tmp_path):
    ctx, seen = context(tmp_path, lambda r: sse_response(sse(STARTED, complete("not_found"))))
    assert await SwapWorker().run(ctx) == []
    assert len(seen) == 1
    assert ctx.log.events[-1].data["outcome"] == "not_found"


async def test_dropped_stream_is_recovered_by_polling_the_run(tmp_path):
    polls = iter(["RUNNING", "COMPLETED"])

    def handler(request):
        if request.url == AGENT_SSE_URL:
            return sse_response(sse(STARTED, PROGRESS))
        assert str(request.url) == f"{RUNS_URL}/r1"
        status = next(polls)
        result = REAL_RESULT if status == "COMPLETED" else None
        return httpx.Response(200, json={"run_id": "r1", "status": status, "result": result})

    ctx, seen = context(tmp_path, handler)
    target = SwapTarget(name="t", url=TEKNIC.url, goal="g")
    events = [e async for e in ctx.tf.agent_run(target.url, "g", {})]
    assert events[-1].type == "COMPLETE" and events[-1].recovered
    assert [r.method for r in seen] == ["POST", "GET", "GET"]


async def test_stream_dropped_before_the_run_started_is_an_error(tmp_path):
    def handler(request):
        raise httpx.ReadError("connection reset")

    ctx, _ = context(tmp_path, handler)
    with pytest.raises(httpx.ReadError):
        [e async for e in ctx.tf.agent_run(TEKNIC.url, "g", {})]


@pytest.mark.parametrize("missing", ["country_of_origin", "origin_quote", "origin_source_url"])
def test_origin_claim_needs_country_quote_and_page(missing):
    result = REAL_RESULT | {missing: None}
    claims = claims_from_candidate(AgentMotorCandidate.model_validate(result), "r1", True)
    assert "country_of_origin" not in {c.field for c in claims}


async def test_a_list_result_is_an_incomplete_run_and_the_other_site_still_counts(tmp_path):
    """Seen live on scribd.com: the agent ignored the schema and returned a list. That used to
    raise out of the worker and fail the whole job."""
    bad = SwapTarget(name="bad", url="https://bad.example/", goal="g")

    def handler(request):
        if json.loads(request.content)["url"] == bad.url:
            listed = complete() | {"result": [{"date": "Apr 25, 2025"}]}
            return sse_response(sse(STARTED, listed))
        return sse_response(sse(STARTED, complete()))

    ctx, _ = context(tmp_path, handler)
    [candidate] = await SwapWorker(targets=(TEKNIC, bad)).run(ctx)
    assert candidate.id == "CPM-SDSK-2310D-RLN"
    finished = [e.data for e in ctx.log.events if e.type == "run_finished"]
    assert sorted(f["outcome"] for f in finished) == ["incomplete", "success"]
    assert any("returned a list" in f["reason"] for f in finished)


async def test_a_result_that_does_not_fit_the_schema_costs_only_that_site(tmp_path):
    odd = complete() | {"result": {"status": "success", "specs": "none"}}
    ctx, _ = context(tmp_path, lambda r: sse_response(sse(STARTED, odd)))
    assert await SwapWorker().run(ctx) == []
    assert [e.data["stage"] for e in ctx.log.events if e.type == "error"] == ["EXTRACT"]
