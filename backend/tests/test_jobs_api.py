import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.orchestrator.job import PIPELINE, VERIFY_PASSES
from app.orchestrator.workers import FAKE_HTML, FAKE_URL
from app.tfclient.recorder import Recorder


class NoClaimWorker:
    name = "swap:none"

    async def run(self, ctx):
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "replay_speed", 0)
    with TestClient(app) as c:
        yield c


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


@pytest.mark.parametrize(("mode", "worker"), [("replay", "FakeSwapWorker"), ("live", "SwapWorker")])
def test_mode_picks_the_worker(client, mode, worker):
    workers = client.app.state.runtime.workers(mode)
    assert [type(w).__name__ for w in workers] == [worker]


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

    def __init__(self, url, kind="page"):
        self.url, self.kind = url, kind

    async def run(self, ctx):
        from datetime import UTC, datetime

        from app.schemas import Claim, Source

        source = Source(url=self.url, kind=self.kind, fetched_at=datetime.now(UTC), via="replay")
        return [
            Claim(
                id="c1",
                candidate_id="m1",
                field="price",
                raw_value="1",
                raw_unit=None,
                quote="q 1",
                source=source,
                extracted_by="tinyagent",
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
