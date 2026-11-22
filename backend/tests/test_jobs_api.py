import json

import pytest

from app.agents.verifier import canonical_url
from app.config import settings
from app.orchestrator.job import PIPELINE, VERIFY_PASSES
from app.orchestrator.workers import FAKE_HTML, FAKE_URL
from app.tfclient.recorder import Recorder


class NoClaimWorker:
    name = "swap:none"

    async def run(self, ctx):
        return []


def sse_events(client, job_id, last_event_id=None):
    headers = {"Last-Event-ID": str(last_event_id)} if last_event_id is not None else {}
    with client.stream("GET", f"/api/jobs/{job_id}/events", headers=headers) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        return [json.loads(line[5:]) for line in r.iter_lines() if line.startswith("data:")]


def start(client, worker=None):
    if worker is not None:
        client.app.state.runtime.workers = lambda mode: [worker]
    r = client.post("/api/jobs", json={"mode": "replay"})
    assert r.status_code == 201
    return r.json()["job_id"]


def test_job_streams_every_stage_and_ends_done(client):
    events = sse_events(client, start(client, NoClaimWorker()))
    stages = [e["data"]["stage"] for e in events if e["type"] == "stage"]
    assert stages == [*PIPELINE, "DONE"]
    assert all(set(e) == {"id", "type", "job_id", "ts", "data"} for e in events)
    compliance = next(e for e in events if e["type"] == "compliance")
    assert "domestic_pct" in compliance["data"]["card"]


def test_last_event_id_resumes_after_that_event(client):
    job_id = start(client, NoClaimWorker())
    everything = sse_events(client, job_id)
    assert sse_events(client, job_id, last_event_id=3) == everything[3:]


def test_status_reports_final_stage(client):
    job_id = start(client, NoClaimWorker())
    sse_events(client, job_id)
    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["stage"] == "DONE" and body["mode"] == "replay"


def test_unknown_job_is_404(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404


@pytest.mark.parametrize("mode", ["replay", "live", "mixed"])
def test_every_mode_runs_the_swap_worker(client, mode):
    workers = client.app.state.runtime.workers(mode)
    assert [type(w).__name__ for w in workers] == ["SwapWorker"]


def test_recorded_teknic_job_replays_offline(client):
    client.app.state.runtime.cad = fake_cad([])
    events = sse_events(client, start(client))
    assert events[-1]["data"]["stage"] == "DONE"
    finished = next(e for e in events if e["type"] == "run_finished")["data"]
    assert finished["outcome"] == "success" and finished["live"] is False
    verified = {e["data"]["claim"]["field"] for e in events if e["type"] == "claim_verified"}
    assert verified == {
        "supply_voltage_min",
        "supply_voltage_max",
        "body_length",
        "shaft_diameter",
        "country_of_origin",
        "continuous_torque",
        "peak_torque",
        "max_speed",
    }
    by_dom = {
        e["data"]["claim"]["field"]
        for e in events
        if e["type"] == "claim_verified" and e["data"]["claim"]["verify_method"] == "agent_dom"
    }
    assert by_dom == {"continuous_torque", "peak_torque", "max_speed"}
    [design] = [
        e["data"]
        for e in events
        if e["type"] == "design_ready" and e["data"]["role"] == "candidate"
    ]
    assert design["part_number"] == "CPM-SDSK-2310S-RLN"
    assert design["origin"]["tier"] == "T1"
    torque = next(
        e["data"]["check"]
        for e in events
        if e["type"] == "check_result" and e["data"]["check"]["check"] == "torque_cont"
    )
    assert torque["verdict"] == "pass"


def test_claims_missing_from_main_content_are_found_in_the_tables_pass(
    client, monkeypatch, tmp_path
):
    import asyncio

    url = "https://tables.invalid/p"
    pages = {None: "<p>Overview only</p>", "table": "<table><td>q 1</td></table>"}
    for selectors in VERIFY_PASSES:
        request = {"urls": [url], "format": "html", "ttl": 0}
        if selectors:
            request["include_selectors"] = selectors
        text = pages[selectors[0] if selectors else None]

        async def response(text=text):
            return {"results": [{"url": url, "text": text}], "errors": []}

        asyncio.run(Recorder(tmp_path, "live").call("fetch", request, response))
    monkeypatch.setattr(settings, "recordings_dir", tmp_path)
    events = sse_events(client, start(client, ClaimWorker(url)))
    assert [e["type"] for e in events if e["type"].startswith("claim_")] == ["claim_verified"]


def test_fake_worker_recording_matches_the_fake_page():
    request = {"urls": [FAKE_URL], "format": "html", "ttl": 0}
    path = Recorder(settings.recordings_dir, "replay").path("fetch", request)
    assert path.exists(), "run: uv run python -m scripts.make_fake_recording"
    import gzip

    with gzip.open(path, "rt") as f:
        saved = json.load(f)
    assert saved["response"]["fake"] is True
    assert saved["response"]["results"][0]["text"] == FAKE_HTML


def test_existing_frontend_endpoints_are_unchanged(client):
    assert client.get("/health").json() == {"status": "ok"}
    for path in ("/api/robot", "/api/compliance", "/api/candidates/seed", "/api/designs"):
        assert client.get(path).status_code == 200


class BrokenWorker:
    name = "swap:broken"

    async def run(self, ctx):
        raise RuntimeError("site exploded")


def test_worker_crash_ends_job_failed_with_error_event(client):
    events = sse_events(client, start(client, BrokenWorker()))
    error = next(e for e in events if e["type"] == "error")
    assert error["data"] == {"message": "RuntimeError: site exploded", "stage": "EXTRACT"}
    assert events[-1]["data"]["stage"] == "FAILED"


class ClaimWorker:
    name = "swap:claims"

    def __init__(self, url, kind="page", run_id=None):
        self.url, self.kind, self.run_id = url, kind, run_id

    async def run(self, ctx):
        from datetime import UTC, datetime

        from app.orchestrator.workers import NO_ORIGIN
        from app.schemas import Candidate, Claim, Source

        source = Source(
            url=self.url,
            kind=self.kind,
            fetched_at=datetime.now(UTC),
            via="replay",
            run_id=self.run_id,
        )
        claim = Claim(
            id="c1",
            candidate_id="m1",
            field="price",
            raw_value="1",
            raw_unit=None,
            quote="q 1",
            source=source,
            extracted_by="tinyagent",
        )
        return [
            Candidate(
                id="m1",
                manufacturer=None,
                part_number=None,
                motor_type="unknown",
                nema_frame=None,
                claims=[claim],
                origin=NO_ORIGIN,
                status="found",
            )
        ]


def rejections(events):
    return [e["data"]["reason"] for e in events if e["type"] == "claim_rejected"]


def test_pdf_claims_are_rejected_until_pdf_verification_exists(client):
    events = sse_events(client, start(client, ClaimWorker("https://x/a.pdf", kind="pdf")))
    assert rejections(events) == ["pdf verification not built"]
    assert events[-1]["data"]["stage"] == "DONE"


def test_failed_fresh_fetch_rejects_the_claims(client, monkeypatch, tmp_path):
    import asyncio

    url = "https://down.invalid/p"

    async def fetch_error():
        return {"results": [], "errors": [{"url": url, "error": "target_http_error"}]}

    for selectors in VERIFY_PASSES:
        request = {"urls": [url], "format": "html", "ttl": 0}
        if selectors:
            request["include_selectors"] = selectors
        asyncio.run(Recorder(tmp_path, "live").call("fetch", request, fetch_error))
    monkeypatch.setattr(settings, "recordings_dir", tmp_path)
    events = sse_events(client, start(client, ClaimWorker(url)))
    assert rejections(events) == ["fresh fetch failed"]


def test_unrecorded_page_in_replay_fails_the_job(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "recordings_dir", tmp_path)
    events = sse_events(client, start(client, ClaimWorker("https://never.invalid/")))
    error = next(e for e in events if e["type"] == "error")
    assert error["data"]["message"].startswith("ReplayMiss") and error["data"]["stage"] == "VERIFY"


def record(tmp_path, product, request, response):
    import asyncio

    async def fn():
        return response

    asyncio.run(Recorder(tmp_path, "live").call(product, request, fn))


def snapshot_job(client, monkeypatch, tmp_path, snapshots):
    """A claim (quote 'q 1') on a JS-filled page: both fetch passes miss it; `snapshots` are
    the run's step DOMs, oldest first (None = TinyFish has no snapshot for that step)."""
    url = "https://maker.invalid/model/A1/?v=75"
    for selectors in VERIFY_PASSES:
        request = {"urls": [url], "format": "html", "ttl": 0}
        if selectors:
            request["include_selectors"] = selectors
        record(tmp_path, "fetch", request, {"results": [{"url": url, "text": "<td></td>"}]})
    steps = [{"id": f"s{i}", "action": "a"} for i in range(len(snapshots))]
    record(tmp_path, "agent", {"op": "run_steps", "run_id": "r9"}, {"steps": steps})
    for step, html in zip(steps, snapshots, strict=True):
        ids = {"run_id": "r9", "step_id": step["id"]}
        canonical = canonical_url(html) if html else None
        record(tmp_path, "agent", {"op": "step_canonical"} | ids, {"canonical": canonical})
        record(tmp_path, "agent", {"op": "step_html"} | ids, {"html": html})
    monkeypatch.setattr(settings, "recordings_dir", tmp_path)
    events = sse_events(client, start(client, ClaimWorker(url, run_id="r9")))
    assert events[-1]["data"]["stage"] == "DONE"
    return [e for e in events if e["type"].startswith("claim_")]


def page(canonical, body):
    return f'<html><head><link rel="canonical" href="{canonical}"></head><body>{body}</body></html>'


def test_js_filled_value_verifies_on_the_agents_snapshot_of_that_page(
    client, monkeypatch, tmp_path
):
    snaps = [
        page("https://maker.invalid/list/", "x"),
        page("https://maker.invalid/model/A1", "q 1"),
        None,
    ]
    [event] = snapshot_job(client, monkeypatch, tmp_path, snaps)
    assert event["type"] == "claim_verified"
    assert event["data"]["claim"]["verify_method"] == "agent_dom"


def test_snapshot_of_another_page_does_not_count(client, monkeypatch, tmp_path):
    snaps = [page("https://maker.invalid/model/B2/", "q 1")]
    [event] = snapshot_job(client, monkeypatch, tmp_path, snaps)
    assert event["type"] == "claim_rejected"


def test_snapshot_without_canonical_does_not_count(client, monkeypatch, tmp_path):
    [event] = snapshot_job(client, monkeypatch, tmp_path, ["<html><body>q 1</body></html>"])
    assert event["type"] == "claim_rejected"


def test_only_the_latest_snapshot_of_the_page_counts(client, monkeypatch, tmp_path):
    canonical = "https://maker.invalid/model/A1/"
    snaps = [page(canonical, "q 1"), page(canonical, "q 2")]
    [event] = snapshot_job(client, monkeypatch, tmp_path, snaps)
    assert event["type"] == "claim_rejected"


def fake_cad(built):
    import httpx

    from app.cad_client import CadClient

    def handler(request):
        if request.method == "POST":
            body = json.loads(request.content)
            built.append(body)
            fit = {
                "envelope_used_mm": 66.0,
                "inboard_room_mm": 100.0,
                "fit_envelope": True,
                "ground_clearance_mm": 20.4,
                "fit_ground": True,
                "params": {"min_ground_clearance": 10.0},
                "wheel_bore_mm": 6.35,
                "needs_hub_adapter": False,
                "shaft_diameter_mm": 6.35,
            }
            d = body["design_id"]
            return httpx.Response(
                200,
                json={"design_id": d, "glb_url": f"/designs/{d}/glb", "step_url": "s", "fit": fit},
            )
        if request.url.path.endswith("/glb"):
            return httpx.Response(200, content=b"glTF-bytes")
        return httpx.Response(404)

    return CadClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), "http://cad.test")


def test_fake_job_checks_ranks_and_publishes_a_design(client):
    from app.orchestrator.workers import FakeSwapWorker

    built = []
    client.app.state.runtime.cad = fake_cad(built)
    events = sse_events(client, start(client, FakeSwapWorker()))
    checks = {
        e["data"]["check"]["check"]: e["data"]["check"]
        for e in events
        if e["type"] == "check_result"
    }
    assert checks["torque_cont"]["verdict"] == "pass"
    assert checks["voltage"]["verdict"] == "review"
    baseline, design = [e["data"] for e in events if e["type"] == "design_ready"]
    assert baseline["role"] == "baseline" and baseline["frame"] == "23"
    assert design["role"] == "candidate" and design["label"].startswith("After: ")
    assert design["verdict"] == "review" and design["fit_badge"] == "needs_review"
    assert design["origin"]["tier"] == "T1"
    assert design["objectives"] == ["performance", "us_first"]
    assert design["glb_url"] == f"/designs/{design['design_id']}/glb"  # served via /cad
    assert built == [
        {"design_id": design["design_id"], "frame": "23", "wheel_r": 60.0, "highlight": True},
        {"design_id": baseline["design_id"], "frame": "23", "wheel_r": 60.0, "highlight": False},
    ]
    glb = client.get(f"/api/designs/{design['design_id']}/glb")
    assert glb.status_code == 200 and glb.content == b"glTF-bytes"
    assert client.get(f"/api/designs/{design['design_id']}/step").status_code == 404


def test_unreachable_cad_is_reported_leaves_fit_in_review_and_the_job_finishes(client):
    import httpx

    from app.cad_client import CadClient
    from app.orchestrator.workers import FakeSwapWorker

    def down(request):
        raise httpx.ConnectError("refused")

    cad = CadClient(httpx.AsyncClient(transport=httpx.MockTransport(down)), "http://cad.test")
    client.app.state.runtime.cad = cad
    events = sse_events(client, start(client, FakeSwapWorker()))
    assert not [e for e in events if e["type"] == "design_ready"]
    errors = [e["data"] for e in events if e["type"] == "error"]
    assert {e["stage"] for e in errors} == {"CHECK", "BUILD"}
    assert all("unreachable" in e["message"] for e in errors)
    assert events[-1]["data"]["stage"] == "DONE"
    fits = [
        e["data"]["check"]
        for e in events
        if e["type"] == "check_result" and e["data"]["check"]["check"].startswith("fit")
    ]
    assert {f["verdict"] for f in fits} == {"review"}
    assert client.get("/api/designs/any-id/glb").status_code == 502


def test_design_file_rejects_bad_ids(client):
    assert client.get("/api/designs/..%2Fetc/glb").status_code in (404, 422)
    assert client.get("/api/designs/ok/obj").status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("frame", [None, "other"])
async def test_frames_the_cad_worker_cannot_model_are_not_sent(frame):
    built = []
    assert await fake_cad(built).build("d1", frame, 60.0) is None
    assert built == []


def test_failed_discovery_degrades_the_job_but_seeds_still_run(client, monkeypatch):
    from app.orchestrator.workers import FakeSwapWorker

    monkeypatch.setattr(
        "app.orchestrator.job.plan_queries", lambda project=None: ["never recorded"]
    )
    events = sse_events(client, start(client, FakeSwapWorker()))
    error = next(e["data"] for e in events if e["type"] == "error")
    assert error["stage"] == "DISCOVER" and error["message"].startswith("ReplayMiss")
    assert any(e["type"] == "claim_verified" for e in events)
    assert events[-1]["data"]["stage"] == "DEGRADED"
