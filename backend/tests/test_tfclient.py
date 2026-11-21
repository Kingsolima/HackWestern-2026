import json
import subprocess
import sys

import pytest

from app.agents.motor_schema import SCHEMA_PATH, output_schema
from app.config import REPO_ROOT
from app.tfclient.client import TinyFishClient
from app.tfclient.recorder import FixtureMissing, Recorder, fixture_key

REQ = {
    "url": "https://example.com",
    "goal": "g",
    "browser_profile": "lite",
    "agent_config": {"max_duration_seconds": 60},
}


def test_fixture_key_ignores_dict_order():
    flipped = dict(reversed(list(REQ.items())))
    assert fixture_key("agent", REQ) == fixture_key("agent", flipped)
    assert fixture_key("agent", REQ) != fixture_key("fetch", REQ)


async def collect(client: TinyFishClient) -> list[dict]:
    return [
        ev async for ev in client.agent_run_sse(REQ["url"], REQ["goal"], max_duration_seconds=60)
    ]


async def test_replay_returns_recorded_events_marked_not_live(tmp_path):
    rec = Recorder(tmp_path)
    events = [{"type": "STARTED", "run_id": "r1"}, {"type": "COMPLETE", "status": "COMPLETED"}]
    rec.save("agent", REQ, {"events": events})
    out = await collect(TinyFishClient("replay", rec))
    assert [e["type"] for e in out] == ["STARTED", "COMPLETE"]
    assert all(e["live"] is False for e in out)


async def test_replay_missing_fixture_raises(tmp_path):
    with pytest.raises(FixtureMissing):
        await collect(TinyFishClient("replay", Recorder(tmp_path)))


async def test_fetch_replay(tmp_path):
    rec = Recorder(tmp_path)
    rec.save(
        "fetch",
        {"urls": ["https://a.com"], "format": "html", "ttl": 0},
        {"response": {"results": [{"url": "https://a.com", "text": "<p>x</p>"}], "errors": []}},
    )
    out = await TinyFishClient("replay", rec).fetch(["https://a.com"], format="html", ttl=0)
    assert out["results"][0]["text"] == "<p>x</p>" and out["live"] is False


def test_fixture_never_contains_api_key(tmp_path):
    p = Recorder(tmp_path).save("agent", REQ, {"events": []})
    assert "X-API-Key" not in p.read_text()


def test_v3_schema_passes_tinyfish_rules():
    checker = REPO_ROOT / "spikes" / "check_tf_schema.py"
    r = subprocess.run([sys.executable, str(checker), str(SCHEMA_PATH)], capture_output=True)
    assert r.returncode == 0, r.stdout.decode()
    assert output_schema() == json.loads(SCHEMA_PATH.read_text())


async def test_recorded_teknic_run_replays_and_matches_schema():
    """Fails if the Teknic goal or schema changes without re-recording the fixture."""
    from app.agents.motor_schema import TfMotorCandidate
    from app.agents.teknic import TEKNIC_URL, build_goal

    events = [
        ev
        async for ev in TinyFishClient("replay").agent_run_sse(
            TEKNIC_URL, build_goal(), output_schema(), max_duration_seconds=240
        )
    ]
    complete = events[-1]
    assert complete["type"] == "COMPLETE" and complete["live"] is False
    cand = TfMotorCandidate.model_validate(complete["result"])
    assert cand.nema_frame == "23" and cand.part_number and cand.specs
