"""TinyFish HTTP client. Every call goes through the Recorder, so each result carries `live`.

Endpoints and fields follow the OpenAPI specs at agent.tinyfish.ai/v1/openapi/{main,search,fetch}
(read Nov 21, 2026).
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict

from app.schemas import AgentRunResult, TfStatus
from app.tfclient.recorder import Recorder

SEARCH_URL = "https://api.search.tinyfish.ai/"
FETCH_URL = "https://api.fetch.tinyfish.ai/"
AGENT_SSE_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"


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
    live: bool


class TFClient:
    def __init__(self, recorder: Recorder, http: httpx.AsyncClient, api_key: str) -> None:
        self.recorder = recorder
        self._http = http
        self._headers = {"X-API-Key": api_key}

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
    ) -> Fetched:
        """ttl=0 forces a fresh fetch; the Verifier always uses it."""
        request: dict[str, Any] = {"urls": urls, "format": format}
        if ttl is not None:
            request["ttl"] = ttl

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
            timeout = httpx.Timeout(30.0, read=None)
            async with self._http.stream(
                "POST", AGENT_SSE_URL, json=request, headers=self._headers, timeout=timeout
            ) as r:
                r.raise_for_status()
                async for event in parse_sse(r.aiter_lines()):
                    if event.get("type") != "HEARTBEAT":
                        yield event

        async for event, is_live in self.recorder.stream("agent", request, live):
            yield AgentEvent.model_validate(event | {"live": is_live})


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
