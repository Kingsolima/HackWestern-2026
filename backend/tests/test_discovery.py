import json

import httpx
import pytest

from app.agents.targets import TEKNIC
from app.agents.triage import Lead
from app.api.routes import load_demo_robot
from app.cad_client import CadClient
from app.orchestrator.board import MemoryBoard
from app.orchestrator.context import JobContext
from app.orchestrator.discovery import MAX_LEADS, classify, discover, keep_leads
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.orchestrator.workers import MAX_AGENT_LEADS, SwapWorker
from app.tfclient.client import AGENT_SSE_URL, TFClient
from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder

pytestmark = pytest.mark.anyio

SLOTS = {"agent": 2, "search": 2, "fetch": 2, "gemini": 2}


def context(tmp_path, handler, mode="live"):
    seen: list[httpx.Request] = []

    def record(request):
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(record))
    recorder = Recorder(tmp_path, mode, replay_speed=0)
    ctx = JobContext(
        job_id="j1",
        mode=mode,
        robot=load_demo_robot(),
        log=EventLog("j1"),
        tf=TFClient(recorder, http, api_key="k", poll_s=0),
        fleet=Fleet(SLOTS),
        budget=JobBudget(),
        board=MemoryBoard(),
        cad=CadClient(http, "http://cad.invalid"),
        gemini=GeminiClient(recorder, http, "g", "flash"),
    )
    return ctx, seen


def test_keep_leads_drops_marketplaces_and_caps_per_site_and_total():
    urls = [
        ("https://www.amazon.com/dp/1", None),
        ("https://www.teknic.com/a", "A"),
        ("https://teknic.com/b", None),
        ("https://teknic.com/c", None),
        ("https://teknic.com/a", None),
        *((f"https://maker{i}.com/m", None) for i in range(20)),
    ]
    leads = keep_leads(urls)
    assert len(leads) == MAX_LEADS
    assert [lead.domain for lead in leads[:3]] == ["teknic.com", "teknic.com", "maker0.com"]
    assert leads[0].title == "A"
    assert not any("amazon" in lead.domain for lead in leads)


async def test_discover_runs_each_query_and_reports_it_as_a_search_run(tmp_path):
    def handler(request):
        q = request.url.params["query"]
        return httpx.Response(200, json={"results": [{"url": f"https://m.com/{len(q)}"}]})

    ctx, seen = context(tmp_path, handler)
    leads = await discover(ctx, ["a", "bb"])
    assert [lead.url for lead in leads] == ["https://m.com/1", "https://m.com/2"]
    assert all(r.url.params["location"] == "US" for r in seen)
    runs = [e.data for e in ctx.log.events if e.type == "run_started"]
    assert [(r["product"], r["goal"]) for r in runs] == [("search", "a"), ("search", "bb")]


async def test_classify_returns_probabilities_for_every_label(tmp_path):
    answer = {
        "type": "choice",
        "choice": "readable_specs",
        "confidence": 0.9,
        "probabilities": {"readable_specs": 0.9, "needs_interaction": 0.1},
    }
    ctx, seen = context(tmp_path, lambda r: httpx.Response(200, json={"answers": {"q": answer}}))
    got = await classify(ctx, "run", "page text")
    assert got == {
        "readable_specs": 0.9,
        "needs_interaction": 0.1,
        "not_a_product_page": 0.0,
        "blocked_or_captcha": 0.0,
    }
    body = json.loads(seen[0].content)
    assert body["model"] == "gemini-decision-1"
    assert set(body["questions"]["q"]["criteria"]) == set(got)
    assert seen[0].headers["x-goog-api-key"] == "g"


@pytest.mark.parametrize("mode", ["live", "replay"])
async def test_classify_failure_falls_back_to_none(tmp_path, mode):
    ctx, _ = context(tmp_path, lambda r: httpx.Response(403, json={"error": "denied"}), mode=mode)
    assert await classify(ctx, "run", "page text") is None
    note = ctx.log.events[-1].data["purpose"]
    assert note.startswith("Decision 1 unavailable")


FLASH_OUT = {
    "status": "success",
    "reason": "ok",
    "manufacturer": "Maker",
    "part_number": "M-23",
    "motor_type": "bldc",
    "nema_frame": "23",
    "specs": [
        {
            "name": "continuous_torque",
            "value": 60,
            "unit": "oz-in",
            "at_speed_value": None,
            "at_speed_unit": None,
            "quote": "Continuous torque 60 oz-in",
            "source_url": "https://elsewhere.example/x",
        }
    ],
    "country_of_origin": "USA",
    "origin_quote": "Made in USA",
    "origin_source_url": "https://elsewhere.example/about",
    "product_url": "https://elsewhere.example/x",
    "datasheet_url": None,
}


def flash_response(obj):
    return httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]}
    )


SSE_OK = (
    'data: {"type":"STARTED","run_id":"r1","timestamp":"2026-11-21T20:00:00+00:00"}\n\n'
    'data: {"type":"COMPLETE","run_id":"r1","status":"COMPLETED","result":null,'
    '"timestamp":"2026-11-21T20:00:10+00:00"}\n\n'
)


async def test_readable_leads_are_extracted_by_gemini_and_pinned_to_the_page(tmp_path):
    def handler(request):
        if "generateContent" in request.url.path:
            return flash_response(FLASH_OUT)
        return httpx.Response(200, text=SSE_OK, headers={"content-type": "text/event-stream"})

    ctx, seen = context(tmp_path, handler)
    lead = Lead(
        url="https://maker.example/m23", domain="maker.example", route="readable", text="specs"
    )
    ctx.leads = [lead]
    candidates = await SwapWorker(targets=[]).run(ctx)
    [candidate] = candidates
    assert candidate.product_url == lead.url
    assert {c.source.url for c in candidate.claims} == {lead.url}
    assert {c.extracted_by for c in candidate.claims} == {"gemini_text"}
    assert {c.source.run_id for c in candidate.claims} == {None}
    assert {c.source.via for c in candidate.claims} == {"tinyfetch"}
    assert not any(r.url == AGENT_SSE_URL for r in seen)


@pytest.mark.parametrize("bad", [{"status": "not_found"}, {"specs": "oops"}])
async def test_failed_extraction_yields_no_candidate(tmp_path, bad):
    ctx, _ = context(tmp_path, lambda r: flash_response(FLASH_OUT | bad))
    ctx.leads = [
        Lead(url="https://maker.example/m", domain="maker.example", route="readable", text="t")
    ]
    assert await SwapWorker(targets=[]).run(ctx) == []
    finished = [e.data for e in ctx.log.events if e.type == "run_finished"]
    assert finished[0]["outcome"] in ("not_found", "error")


async def test_click_leads_get_the_generic_goal_seed_sites_are_skipped_and_capped(tmp_path):
    ctx, seen = context(
        tmp_path,
        lambda r: httpx.Response(200, text=SSE_OK, headers={"content-type": "text/event-stream"}),
    )
    ctx.leads = [
        Lead(url="https://teknic.com/x", domain="teknic.com", route="needs_interaction"),
        *(
            Lead(url=f"https://m{i}.com/", domain=f"m{i}.com", route="needs_interaction")
            for i in range(4)
        ),
        Lead(url="https://dead.com/", domain="dead.com", route="dead"),
    ]
    await SwapWorker(targets=[TEKNIC]).run(ctx)
    urls = [json.loads(r.content)["url"] for r in seen if r.url == AGENT_SSE_URL]
    assert urls[0] == TEKNIC.url
    assert urls[1:] == [f"https://m{i}.com/" for i in range(MAX_AGENT_LEADS)]
    generic = json.loads(next(r.content for r in seen if b"m0.com" in r.content))
    assert generic["goal"].startswith("You are a sourcing engineer")
    assert "Starting from this page" in generic["goal"]


async def test_flash_nulls_for_reason_and_spec_urls_are_filled_from_the_page(tmp_path):
    out = FLASH_OUT | {"reason": None}
    out["specs"] = [FLASH_OUT["specs"][0] | {"source_url": None}]
    ctx, seen = context(tmp_path, lambda r: flash_response(out))
    ctx.leads = [
        Lead(url="https://maker.example/m", domain="maker.example", route="readable", text="t")
    ]
    [candidate] = await SwapWorker(targets=[]).run(ctx)
    assert {c.source.url for c in candidate.claims} == {"https://maker.example/m"}
    body = json.loads(seen[0].content)
    assert "responseSchema" not in body["generationConfig"]
    assert "JSON Schema" in body["contents"][0]["parts"][0]["text"]
