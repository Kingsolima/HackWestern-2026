"""TinyFish client with record/replay. Every TinyFish call in the backend goes through here.

Modes:
- live:   call TinyFish, tag events/results live=True, record a fixture.
- replay: serve the recorded fixture, tag live=False, no network. Missing -> FixtureMissing.

API (docs.tinyfish.ai, checked 2026-11-21): auth is the X-API-Key header.
- Agent SSE: POST https://agent.tinyfish.ai/v1/automation/run-sse
  events STARTED, STREAMING_URL, PROGRESS, HEARTBEAT, COMPLETE{status,result,error}.
  COMPLETED does not mean the goal succeeded; check the result.
- Fetch:     POST https://api.fetch.tinyfish.ai  {urls<=10, format, ttl} -> {results, errors}
`agent_config.max_steps` is beta (403 without access); only max_duration_seconds is sent.
"""

import json
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx

from app.config import settings
from app.tfclient.recorder import Recorder

AGENT_SSE_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"
RUNS_URL = "https://agent.tinyfish.ai/v1/runs"
FETCH_URL = "https://api.fetch.tinyfish.ai"

Mode = Literal["live", "replay"]


class TinyFishError(RuntimeError):
    pass


class TinyFishClient:
    def __init__(self, mode: Mode | None = None, recorder: Recorder | None = None):
        self.mode: Mode = mode or settings.tf_mode  # type: ignore[assignment]
        if self.mode not in ("live", "replay"):
            raise ValueError(f"TF mode must be live or replay, got {self.mode!r}")
        self.recorder = recorder or Recorder()

    def _headers(self) -> dict[str, str]:
        if not settings.tinyfish_api_key:
            raise TinyFishError("TINYFISH_API_KEY is not set in .env")
        return {"X-API-Key": settings.tinyfish_api_key, "Content-Type": "application/json"}

    async def agent_run_sse(
        self,
        url: str,
        goal: str,
        output_schema: dict[str, Any] | None = None,
        max_duration_seconds: int = 240,
        browser_profile: Literal["lite", "stealth"] = "lite",
    ) -> AsyncIterator[dict[str, Any]]:
        request = self.agent_request(
            url, goal, output_schema, max_duration_seconds, browser_profile
        )

        if self.mode == "replay":
            for event in self.recorder.load("agent", request)["events"]:
                yield {**event, "live": False}
            return

        events: list[dict[str, Any]] = []
        timeout = httpx.Timeout(10.0, read=max_duration_seconds + 60)
        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                async with http.stream(
                    "POST", AGENT_SSE_URL, headers=self._headers(), json=request
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode(errors="replace")[:500]
                        raise TinyFishError(f"agent run-sse HTTP {resp.status_code}: {body}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        event = json.loads(line[5:].strip())
                        if event.get("type") == "HEARTBEAT":
                            continue
                        events.append(event)
                        yield {**event, "live": True}
        finally:
            # Record whatever arrived, even a partial stream, so a failed run is inspectable.
            if events:
                self.recorder.save("agent", request, {"events": events})

    async def get_run(self, run_id: str) -> dict[str, Any]:
        """GET /v1/runs/{id}. Use it to recover a run whose SSE stream dropped; never
        re-submit a run before this shows it terminal (docs/design/04-architecture.md §5)."""
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(f"{RUNS_URL}/{run_id}", headers=self._headers())
        if resp.status_code != 200:
            raise TinyFishError(f"get run HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    def record_recovered_run(
        self, request: dict[str, Any], run: dict[str, Any], seen: list[dict[str, Any]]
    ) -> None:
        """Save a fixture for a run recovered via get_run: the events seen before the drop
        plus a COMPLETE event rebuilt from the run object."""
        complete = {
            "type": "COMPLETE",
            "run_id": run.get("run_id"),
            "status": run.get("status"),
            "result": run.get("result"),
            "error": run.get("error"),
            "timestamp": run.get("finished_at"),
        }
        self.recorder.save(
            "agent", request, {"events": [*seen, complete], "recovered_from_run": True}
        )

    @staticmethod
    def agent_request(
        url: str,
        goal: str,
        output_schema: dict[str, Any] | None,
        max_duration_seconds: int,
        browser_profile: str,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "url": url,
            "goal": goal,
            "browser_profile": browser_profile,
            "agent_config": {"max_duration_seconds": max_duration_seconds},
        }
        if output_schema is not None:
            request["output_schema"] = output_schema
        return request

    async def fetch(
        self,
        urls: list[str],
        format: Literal["markdown", "html", "json"] = "markdown",
        ttl: int | None = None,
        include_selectors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch 1-10 urls. The default extraction strips boilerplate and can drop spec
        tables (seen on teknic.com); pass include_selectors=["table"] for verification."""
        if not 1 <= len(urls) <= 10:
            raise ValueError("fetch takes 1-10 urls")
        request: dict[str, Any] = {"urls": urls, "format": format}
        if ttl is not None:
            request["ttl"] = ttl
        if include_selectors:
            request["include_selectors"] = include_selectors

        if self.mode == "replay":
            return {**self.recorder.load("fetch", request)["response"], "live": False}

        async with httpx.AsyncClient(timeout=150.0) as http:
            resp = await http.post(FETCH_URL, headers=self._headers(), json=request)
        if resp.status_code != 200:
            raise TinyFishError(f"fetch HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        self.recorder.save("fetch", request, {"response": data})
        return {**data, "live": True}
