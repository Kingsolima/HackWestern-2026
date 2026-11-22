"""extract_json_live says whether a reading was made now or replayed, so a mixed job does not
show a replayed page as a live find."""

import json

import httpx
import pytest

from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder

ANSWER = {"candidates": [{"content": {"parts": [{"text": json.dumps({"ok": 1})}]}}]}


def client(recorder: Recorder, calls: list) -> tuple[GeminiClient, httpx.AsyncClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=ANSWER)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GeminiClient(recorder, http, "key", "flash"), http


@pytest.mark.anyio
async def test_a_mixed_job_reports_a_recorded_reading_as_replayed(tmp_path):
    calls: list = []
    gemini, http = client(Recorder(tmp_path, "mixed", replay_speed=0), calls)
    async with http:
        first = await gemini.extract_json_live("read this", {"type": "object"})
        again = await gemini.extract_json_live("read this", {"type": "object"})
    assert first == ({"ok": 1}, True)  # nothing recorded yet: a real call, now saved
    assert again == ({"ok": 1}, False)  # same request: replayed, no second call
    assert len(calls) == 1
