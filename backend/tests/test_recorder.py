import gzip
import json

import pytest

from app.tfclient.recorder import Recorder, ReplayMiss, request_key

pytestmark = pytest.mark.anyio


def live_returning(response):
    calls = []

    async def fn():
        calls.append(1)
        return response

    return fn, calls


async def test_live_records_and_replay_returns_it(tmp_path):
    fn, calls = live_returning({"answer": 42})
    assert await Recorder(tmp_path, "live").call("search", {"q": "x"}, fn) == ({"answer": 42}, True)
    replayed = await Recorder(tmp_path, "replay").call("search", {"q": "x"}, fn)
    assert replayed == ({"answer": 42}, False)
    assert len(calls) == 1


async def test_live_mode_ignores_existing_recordings(tmp_path):
    fn, calls = live_returning({"a": 1})
    await Recorder(tmp_path, "live").call("search", {"q": "x"}, fn)
    await Recorder(tmp_path, "live").call("search", {"q": "x"}, fn)
    assert len(calls) == 2


async def test_replay_miss_raises_and_never_calls_live(tmp_path):
    fn, calls = live_returning({})
    with pytest.raises(ReplayMiss):
        await Recorder(tmp_path, "replay").call("fetch", {"urls": ["u"]}, fn)
    assert calls == []


async def test_mixed_replays_hits_and_goes_live_on_misses(tmp_path):
    fn, calls = live_returning({"v": 1})
    await Recorder(tmp_path, "live").call("fetch", {"u": 1}, fn)
    mixed = Recorder(tmp_path, "mixed")
    assert await mixed.call("fetch", {"u": 1}, fn) == ({"v": 1}, False)
    assert await mixed.call("fetch", {"u": 2}, fn) == ({"v": 1}, True)
    assert len(calls) == 2


def test_key_ignores_dict_order_but_not_product():
    assert request_key("fetch", {"a": 1, "b": 2}) == request_key("fetch", {"b": 2, "a": 1})
    assert request_key("fetch", {"a": 1}) != request_key("search", {"a": 1})


async def test_recording_is_gzip_json_with_request(tmp_path):
    fn, _ = live_returning({"r": 1})
    rec = Recorder(tmp_path, "live")
    await rec.call("search", {"q": "x"}, fn)
    with gzip.open(rec.path("search", {"q": "x"}), "rt") as f:
        saved = json.load(f)
    assert saved["request"] == {"q": "x"} and saved["response"] == {"r": 1}


async def test_stream_records_then_replays_in_order(tmp_path):
    async def live():
        for i in range(3):
            yield {"i": i}

    got = [e async for e in Recorder(tmp_path, "live").stream("agent", {"g": 1}, live)]
    assert got == [({"i": i}, True) for i in range(3)]
    replay = Recorder(tmp_path, "replay", replay_speed=0)
    assert [e async for e in replay.stream("agent", {"g": 1}, live)] == [
        ({"i": i}, False) for i in range(3)
    ]


async def test_broken_live_stream_is_not_saved(tmp_path):
    async def live():
        yield {"i": 0}
        raise ConnectionError("dropped")

    rec = Recorder(tmp_path, "live")
    with pytest.raises(ConnectionError):
        async for _ in rec.stream("agent", {"g": 2}, live):
            pass
    assert not rec.path("agent", {"g": 2}).exists()
