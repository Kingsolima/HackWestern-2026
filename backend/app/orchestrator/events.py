"""SSE event contract and the per-job event log.

Every event on the wire is `{id, type, job_id, ts, data}`; the UI is a pure function of the log.
Each payload model owns its `type`, so an event's type and data shape cannot disagree.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel

from app.engineering.compliance import ComplianceCard
from app.schemas import Claim, Outcome, Product

EventType = Literal[
    "stage",
    "run_started",
    "run_streaming_url",
    "run_progress",
    "run_finished",
    "claim_verified",
    "claim_rejected",
    "check_result",
    "compliance",
    "design_ready",
    "advocate",
    "synthesis",
    "error",
]

Stage = Literal[
    "CREATED",
    "COMPLIANCE_BASELINE",
    "PLAN",
    "DISCOVER",
    "TRIAGE",
    "EXTRACT",
    "VERIFY",
    "CHECK",
    "RANK",
    "BUILD",
    "REPORT",
    "DONE",
    "DEGRADED",
    "FAILED",
]
TERMINAL_STAGES: frozenset[Stage] = frozenset({"DONE", "DEGRADED", "FAILED"})


class Payload(BaseModel):
    type: ClassVar[EventType]


class StagePayload(Payload):
    type: ClassVar[EventType] = "stage"
    stage: Stage


class RunStarted(Payload):
    type: ClassVar[EventType] = "run_started"
    run_id: str
    worker: str
    product: Product
    site: str
    url: str | None
    goal: str | None
    live: bool


class RunStreamingUrl(Payload):
    type: ClassVar[EventType] = "run_streaming_url"
    run_id: str
    streaming_url: str


class RunProgress(Payload):
    type: ClassVar[EventType] = "run_progress"
    run_id: str
    purpose: str


class RunFinished(Payload):
    type: ClassVar[EventType] = "run_finished"
    run_id: str
    outcome: Outcome
    reason: str
    duration_s: float
    live: bool


class ClaimVerified(Payload):
    type: ClassVar[EventType] = "claim_verified"
    claim: Claim


class ClaimRejected(Payload):
    type: ClassVar[EventType] = "claim_rejected"
    claim: Claim
    reason: str


class CompliancePayload(Payload):
    type: ClassVar[EventType] = "compliance"
    card: ComplianceCard


class DesignReady(Payload):
    """A design the CAD worker built. One event per design: the baseline robot first, then
    each candidate. Urls are CAD-worker paths (/designs/{id}/glb); the UI serves them via /cad."""

    type: ClassVar[EventType] = "design_ready"
    design_id: str
    role: Literal["baseline", "candidate"]
    label: str
    motor: str
    frame: str
    glb_url: str
    step_url: str
    fit: dict[str, Any]


class ErrorPayload(Payload):
    type: ClassVar[EventType] = "error"
    message: str
    stage: Stage | None


class Event(BaseModel):
    id: int
    type: EventType
    job_id: str
    ts: datetime
    data: dict[str, Any]


class EventLog:
    """Append-only, in-memory log for one job. Subscribers replay from any id, then follow."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._events: list[Event] = []
        self._closed = False
        self._changed = asyncio.Condition()

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    @property
    def closed(self) -> bool:
        return self._closed

    async def emit(self, payload: Payload) -> Event:
        if self._closed:
            raise RuntimeError(f"event log for job {self.job_id} is closed")
        event = Event(
            id=len(self._events) + 1,
            type=payload.type,
            job_id=self.job_id,
            ts=datetime.now(UTC),
            data=payload.model_dump(mode="json"),
        )
        async with self._changed:
            self._events.append(event)
            self._changed.notify_all()
        return event

    async def close(self) -> None:
        async with self._changed:
            self._closed = True
            self._changed.notify_all()

    async def subscribe(self, after_id: int = 0) -> AsyncIterator[Event]:
        """Yield events with id > after_id, then new ones until the log closes."""
        next_index = max(after_id, 0)
        while True:
            async with self._changed:
                while next_index >= len(self._events) and not self._closed:
                    await self._changed.wait()
                batch = self._events[next_index:]
                done = self._closed
            for event in batch:
                yield event
            next_index += len(batch)
            if done and not batch:
                return
