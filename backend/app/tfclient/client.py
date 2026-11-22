"""TinyFish HTTP client. Every call goes through the Recorder, so each result carries `live`.

Endpoints and fields follow the OpenAPI specs at agent.tinyfish.ai/v1/openapi/{main,search,fetch}
(read Nov 21, 2026).
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, model_validator

from app.agents.verifier import canonical_url
from app.schemas import AgentRunResult, TfStatus
from app.tfclient.recorder import Recorder

SEARCH_URL = "https://api.search.tinyfish.ai/"
FETCH_URL = "https://api.fetch.tinyfish.ai/"
AGENT_SSE_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"
RUNS_URL = "https://agent.tinyfish.ai/v1/runs"
TERMINAL: frozenset[str] = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SearchResult(_Loose):
    url: str
    title: str | None = None
    snippet: str | None = None
    site_name: str | None = None


class Searched(_Loose):
    results: list[SearchResult]
    live: bool


class FetchResult(_Loose):
    url: str
    final_url: str | None = None
    title: str | None = None
    format: Literal["markdown", "html", "json"] | None = None
    text: str | dict[str, Any] | None = None


class FetchError(_Loose):
    url: str
    error: str
    status: int | None = None


class Fetched(_Loose):
    results: list[FetchResult]
    errors: list[FetchError]
    live: bool


class AgentEvent(_Loose):
    """One TinyAgent SSE event (STARTED, STREAMING_URL, PROGRESS, COMPLETE, ...)."""

    type: str
    run_id: str | None = None
    timestamp: str | None = None
    streaming_url: str | None = None
    purpose: str | None = None
    status: TfStatus | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    profile_hint: dict[str, Any] | None = None
    recovered: bool = False
    live: bool

    @model_validator(mode="before")
    @classmethod
    def _result_is_an_object(cls, data: Any) -> Any:
        """An agent can ignore the output schema and return a list or a string. That run has no
        usable result (classify_outcome: incomplete); it must not fail the whole job."""
        if isinstance(data, dict) and data.get("result") is not None:
            result = data["result"]
            if not isinstance(result, dict):
                note = f"agent returned a {type(result).__name__}, not the requested object"
                return {**data, "result": None, "error": data.get("error") or note}
        return data


class RunStep(_Loose):
    id: str
    action: str


class TFClient:
    def __init__(
        self, recorder: Recorder, http: httpx.AsyncClient, api_key: str, poll_s: float = 5.0
    ) -> None:
        self.recorder = recorder
        self._http = http
        self._headers = {"X-API-Key": api_key}
        self._poll_s = poll_s

    async def search(self, query: str, **params: str) -> Searched:
        request = {"query": query} | params

        async def live() -> dict[str, Any]:
            r = await self._http.get(SEARCH_URL, params=request, headers=self._headers)
            r.raise_for_status()
            return r.json()

        body, is_live = await self.recorder.call("search", request, live)
        return Searched(results=body.get("results", []), live=is_live)

    async def fetch(
        self,
        urls: list[str],
        format: Literal["markdown", "html", "json"] = "markdown",
        ttl: int | None = None,
        include_selectors: list[str] | None = None,
    ) -> Fetched:
        """ttl=0 forces a fresh fetch; the Verifier always uses it."""
        request: dict[str, Any] = {"urls": urls, "format": format}
        if ttl is not None:
            request["ttl"] = ttl
        if include_selectors:
            request["include_selectors"] = include_selectors

        async def live() -> dict[str, Any]:
            r = await self._http.post(FETCH_URL, json=request, headers=self._headers)
            r.raise_for_status()
            return r.json()

        body, is_live = await self.recorder.call("fetch", request, live)
        return Fetched(results=body.get("results", []), errors=body.get("errors", []), live=is_live)

    async def agent_run(
        self,
        url: str,
        goal: str,
        output_schema: dict[str, Any],
        *,
        stealth: bool = False,
        proxy_country: str | None = None,
        max_duration_s: int = 180,
    ) -> AsyncIterator[AgentEvent]:
        request: dict[str, Any] = {
            "url": url,
            "goal": goal,
            "output_schema": output_schema,
            "browser_profile": "stealth" if stealth else "lite",
            "agent_config": {"max_duration_seconds": max_duration_s},
            "capture_config": {"html": True},
        }
        if proxy_country:
            request["proxy_config"] = {"enabled": True, "country_code": proxy_country}

        async def live() -> AsyncIterator[dict[str, Any]]:
            run_id: str | None = None
            timeout = httpx.Timeout(30.0, read=None)
            try:
                async with self._http.stream(
                    "POST", AGENT_SSE_URL, json=request, headers=self._headers, timeout=timeout
                ) as r:
                    r.raise_for_status()
                    async for event in parse_sse(r.aiter_lines()):
                        run_id = run_id or event.get("run_id")
                        if event.get("type") == "COMPLETE":
                            yield event
                            return
                        if event.get("type") != "HEARTBEAT":
                            yield event
            except httpx.TransportError:
                if run_id is None:
                    raise
            if run_id is None:
                raise RuntimeError("agent stream ended before the run started")
            yield await self._wait_for_run(run_id, deadline_s=max_duration_s + 120)

        async for event, is_live in self.recorder.stream("agent", request, live):
            yield AgentEvent.model_validate(event | {"live": is_live})

    async def run_steps(self, run_id: str) -> list[RunStep]:
        """Steps of a finished run that captured a page snapshot (capture_config html)."""
        request = {"op": "run_steps", "run_id": run_id}

        async def live() -> dict[str, Any]:
            r = await self._http.get(f"{RUNS_URL}/{run_id}", headers=self._headers)
            r.raise_for_status()
            steps = r.json().get("steps") or []
            kept = [
                {"id": s["id"], "action": s.get("action") or ""} for s in steps if s.get("html")
            ]
            return {"steps": kept}

        body, _ = await self.recorder.call("agent", request, live)
        return [RunStep.model_validate(s) for s in body["steps"]]

    async def _step_snapshot(self, run_id: str, step_id: str) -> str | None:
        url = f"{RUNS_URL}/{run_id}/steps/{step_id}/html"
        r = await self._http.get(url, headers=self._headers, follow_redirects=True)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text

    async def step_canonical(self, run_id: str, step_id: str) -> str | None:
        """Canonical URL of the page the agent's browser showed at that step; None if TinyFish
        has no snapshot (404, seen on a run's final step) or the page declares none. Only the
        URL is recorded: snapshots are ~1.4 MB and most are of pages no claim needs."""
        request = {"op": "step_canonical", "run_id": run_id, "step_id": step_id}

        async def live() -> dict[str, Any]:
            snapshot = await self._step_snapshot(run_id, step_id)
            return {"canonical": canonical_url(snapshot) if snapshot else None}

        body, _ = await self.recorder.call("agent", request, live)
        return body["canonical"]

    async def step_html(self, run_id: str, step_id: str) -> str | None:
        """The page DOM as the agent's browser rendered it at that step (recorded in full: it is
        the evidence for agent_dom claims)."""
        request = {"op": "step_html", "run_id": run_id, "step_id": step_id}

        async def live() -> dict[str, Any]:
            return {"html": await self._step_snapshot(run_id, step_id)}

        body, _ = await self.recorder.call("agent", request, live)
        return body["html"]

    async def _wait_for_run(self, run_id: str, deadline_s: float) -> dict[str, Any]:
        """The stream dropped after the run started: poll it to the end, never resubmit
        (the run may still be executing)."""
        give_up = time.monotonic() + deadline_s
        while True:
            r = await self._http.get(f"{RUNS_URL}/{run_id}", headers=self._headers)
            r.raise_for_status()
            run = r.json()
            if run.get("status") in TERMINAL:
                error = run.get("error") or {}
                return {
                    "type": "COMPLETE",
                    "run_id": run_id,
                    "status": run["status"],
                    "result": run.get("result"),
                    "error": error.get("message"),
                    "profile_hint": error.get("profile_hint") or run.get("profile_hint"),
                    "timestamp": run.get("finished_at"),
                    "recovered": True,
                }
            if time.monotonic() > give_up:
                raise TimeoutError(f"run {run_id} still {run.get('status')} after {deadline_s}s")
            await asyncio.sleep(self._poll_s)


async def parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[dict[str, Any]]:
    """Yield the JSON `data:` payload of each SSE event."""
    data: list[str] = []
    async for line in lines:
        if line.startswith("data:"):
            data.append(line[5:].strip())
        elif line == "" and data:
            yield json.loads("\n".join(data))
            data = []
    if data:
        yield json.loads("\n".join(data))


def run_result(events: list[AgentEvent]) -> AgentRunResult:
    """Fold a finished run's events into the shape classify_outcome reads."""
    complete = next((e for e in reversed(events) if e.type == "COMPLETE"), None)
    if complete is None or complete.run_id is None or complete.status is None:
        raise ValueError("run needs a COMPLETE event with run_id and status")
    started = next((e.timestamp for e in events if e.type == "STARTED"), None)
    duration = 0.0
    if started and complete.timestamp:
        duration = (
            datetime.fromisoformat(complete.timestamp) - datetime.fromisoformat(started)
        ).total_seconds()
    hint = (complete.profile_hint or {}).get("reason")
    return AgentRunResult(
        run_id=complete.run_id,
        tf_status=complete.status,
        result=complete.result,
        error=complete.error,
        profile_hint_reason=hint if hint in ("auth_wall", "bot_challenge") else None,
        duration_s=duration,
    )
