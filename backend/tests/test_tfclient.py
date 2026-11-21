import json

import httpx
import pytest

from app.tfclient.client import AGENT_SSE_URL, AgentEvent, TFClient, parse_sse, run_result
from app.tfclient.recorder import Recorder

pytestmark = pytest.mark.anyio

SSE_BODY = (
    'data: {"type":"STARTED","run_id":"r1","timestamp":"2026-11-21T20:00:00+00:00"}\n\n'
    'data: {"type":"STREAMING_URL","run_id":"r1","streaming_url":"https://s/1",'
    '"timestamp":"2026-11-21T20:00:01+00:00"}\n\n'
    'data: {"type":"HEARTBEAT","timestamp":"2026-11-21T20:00:02+00:00"}\n\n'
    'data: {"type":"PROGRESS","run_id":"r1","purpose":"Reading specs",'
    '"timestamp":"2026-11-21T20:00:03+00:00"}\n\n'
    'data: {"type":"COMPLETE","run_id":"r1","status":"COMPLETED","result":{"status":"success"},'
    '"timestamp":"2026-11-21T20:00:42+00:00"}\n\n'
)


def client(tmp_path, mode, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url == AGENT_SSE_URL:
            return httpx.Response(200, text=SSE_BODY, headers={"content-type": "text/event-stream"})
        if request.method == "GET":
            return httpx.Response(200, json={"results": [{"url": "https://a", "title": "A"}]})
        return httpx.Response(200, json={"results": [{"url": "https://a", "text": "<p>x</p>"}]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TFClient(Recorder(tmp_path, mode, replay_speed=0), http, api_key="k")


async def test_search_sends_key_and_query(tmp_path):
    seen = []
    found = await client(tmp_path, "live", seen).search("nema 23 servo", location="US")
    assert found.live and found.results[0].url == "https://a"
    assert seen[0].headers["X-API-Key"] == "k"
    assert seen[0].url.params["query"] == "nema 23 servo"
    assert seen[0].url.params["location"] == "US"


async def test_fetch_passes_ttl_and_replays_offline(tmp_path):
    seen = []
    fresh = await client(tmp_path, "live", seen).fetch(["https://a"], format="html", ttl=0)
    assert json.loads(seen[0].content) == {"urls": ["https://a"], "format": "html", "ttl": 0}
    again = await client(tmp_path, "replay", seen).fetch(["https://a"], format="html", ttl=0)
    assert again.results == fresh.results and not again.live
    assert len(seen) == 1


async def test_agent_run_drops_heartbeats_and_replays(tmp_path):
    seen = []
    live = [e async for e in client(tmp_path, "live", seen).agent_run("https://t", "g", {})]
    assert [e.type for e in live] == ["STARTED", "STREAMING_URL", "PROGRESS", "COMPLETE"]
    assert all(e.live for e in live)
    body = json.loads(seen[0].content)
    assert body["capture_config"] == {"html": True}
    assert body["agent_config"] == {"max_duration_seconds": 180}
    replayed = [e async for e in client(tmp_path, "replay", seen).agent_run("https://t", "g", {})]
    assert [e.type for e in replayed] == [e.type for e in live]
    assert not any(e.live for e in replayed)


async def test_stealth_retry_is_a_different_request(tmp_path):
    seen = []
    tf = client(tmp_path, "live", seen)
    [e async for e in tf.agent_run("https://t", "g", {}, stealth=True, proxy_country="US")]
    body = json.loads(seen[0].content)
    assert body["browser_profile"] == "stealth"
    assert body["proxy_config"] == {"enabled": True, "country_code": "US"}


async def test_parse_sse_joins_multiline_data():
    async def lines():
        for line in ['data: {"a":', "data: 1}", "", 'data: {"b": 2}']:
            yield line

    assert [e async for e in parse_sse(lines())] == [{"a": 1}, {"b": 2}]


def ev(**kw) -> AgentEvent:
    return AgentEvent(live=True, **kw)


def test_run_result_folds_events():
    result = run_result(
        [
            ev(type="STARTED", run_id="r1", timestamp="2026-11-21T20:00:00+00:00"),
            ev(
                type="COMPLETE",
                run_id="r1",
                status="FAILED",
                error="blocked",
                profile_hint={"reason": "bot_challenge", "message": "m", "setup_url": "u"},
                timestamp="2026-11-21T20:00:42+00:00",
            ),
        ]
    )
    assert result.tf_status == "FAILED"
    assert result.profile_hint_reason == "bot_challenge"
    assert result.duration_s == 42


def test_run_result_needs_complete_event():
    with pytest.raises(ValueError):
        run_result([ev(type="STARTED", run_id="r1")])
