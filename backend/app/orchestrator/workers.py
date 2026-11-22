"""Part workers: code loops, one per BOM line (docs/design/07 section 2).

SwapWorker runs TinyAgent on each swap target. FakeSwapWorker is a test double: a made-up page
whose fetches are committed under data/recordings/fetch with `fake: true`.
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol
from urllib.parse import urlparse

from app.agents.targets import MOTOR_SCHEMA, SWAP_TARGETS, SwapTarget
from app.agents.verifier import classify_outcome
from app.engineering.spec_checks import requirement
from app.orchestrator.context import JobContext
from app.orchestrator.events import RunFinished, RunProgress, RunStarted, RunStreamingUrl
from app.schemas import (
    AgentMotorCandidate,
    AgentRunResult,
    Candidate,
    Claim,
    OriginEvidence,
    Outcome,
    Source,
)
from app.tfclient.client import AgentEvent, run_result


class Worker(Protocol):
    name: str

    async def run(self, ctx: JobContext) -> list[Candidate]:
        """Dispatch runs, emit run_* events, return candidates holding raw (unverified) claims."""
        ...


FAKE_URL = "https://example.invalid/fake-motor"
FAKE_HTML = (
    "<html><body><h1>FAKE-23 test motor (not a real product)</h1>"
    "<p>Continuous torque: <b>0.50</b> N-m</p>"
    "<p>Rated speed: 3,000&nbsp;rpm</p>"
    "<p>Regular price $299</p><p>Sale price $265</p>"
    "<p>Made in USA at our Ohio plant.</p></body></html>"
)
_FAKE_CLAIMS = [
    ("continuous_torque", "0.50", "N-m", "Continuous torque: 0.50 N-m"),
    ("rated_speed", "3000", "rpm", "Rated speed: 3,000 rpm"),
    ("price", "265", "USD", "Regular price $299"),
    ("country_of_origin", "US", None, "Made in USA at our Ohio plant."),
]


class FakeSwapWorker:
    """Test double for the swap worker; its run is labelled fake and not live."""

    name = "swap:drive_motor"

    async def run(self, ctx: JobContext) -> list[Candidate]:
        run_id = f"fake-{ctx.job_id}"
        log = ctx.log
        await log.emit(
            RunStarted(
                run_id=run_id,
                worker=self.name,
                product="agent",
                site="example.invalid",
                url=FAKE_URL,
                goal="Fake run: read specs and origin of FAKE-23",
                live=False,
            )
        )
        await log.emit(RunProgress(run_id=run_id, purpose="Fake run: reading the spec table"))
        await log.emit(
            RunFinished(run_id=run_id, outcome="success", reason="fake", duration_s=0, live=False)
        )
        source = Source(url=FAKE_URL, kind="page", fetched_at=datetime.now(UTC), via="replay")
        claims = [
            Claim(
                id=f"{run_id}:{field}",
                candidate_id="fake-23",
                field=field,
                raw_value=value,
                raw_unit=unit,
                quote=quote,
                source=source,
                extracted_by="tinyagent",
            )
            for field, value, unit, quote in _FAKE_CLAIMS
        ]
        return [
            Candidate(
                id="fake-23",
                manufacturer="Fake Motors (not a real product)",
                part_number="FAKE-23",
                motor_type="servo_integrated",
                nema_frame="23",
                claims=claims,
                origin=NO_ORIGIN,
                status="found",
                product_url=FAKE_URL,
            )
        ]


class SwapWorker:
    """Hunts US-made replacements for the drive motor: one TinyAgent run per target, one
    stealth + US-proxy retry when a run is blocked (docs/design/04 section 5)."""

    name = "swap:drive_motor"

    def __init__(self, targets: Sequence[SwapTarget] = SWAP_TARGETS) -> None:
        self.targets = targets

    async def run(self, ctx: JobContext) -> list[Candidate]:
        results = await asyncio.gather(*(self._target(ctx, t) for t in self.targets))
        return [candidate for found in results for candidate in found]

    async def _target(self, ctx: JobContext, target: SwapTarget) -> list[Candidate]:
        outcome, run, live = await self._dispatch(ctx, target, stealth=False)
        if outcome == "blocked":
            outcome, run, live = await self._dispatch(ctx, target, stealth=True)
        if outcome != "success" or run.result is None:
            return []
        output = AgentMotorCandidate.model_validate(run.result)
        return [candidate_from_output(output, run.run_id, live)]

    async def _dispatch(
        self, ctx: JobContext, target: SwapTarget, stealth: bool
    ) -> tuple[Outcome, AgentRunResult, bool]:
        domain = urlparse(target.url).hostname or target.url
        req = requirement(ctx.robot.requirements)
        goal = target.goal_for(req.t_cont_nm, req.t_peak_nm, req.v_bus)
        events: list[AgentEvent] = []
        async with ctx.fleet.slot("agent", ctx.budget, domain):
            async for event in ctx.tf.agent_run(
                target.url,
                goal,
                MOTOR_SCHEMA,
                stealth=stealth,
                proxy_country="US" if stealth else None,
                max_duration_s=target.max_duration_s,
            ):
                events.append(event)
                await self._tile(ctx, target, domain, event)
        run = run_result(events)
        outcome = classify_outcome(run)
        live = events[-1].live
        reason = str((run.result or {}).get("reason") or run.error or "")
        await ctx.log.emit(
            RunFinished(
                run_id=run.run_id,
                outcome=outcome,
                reason=reason,
                duration_s=run.duration_s,
                live=live,
            )
        )
        return outcome, run, live

    async def _tile(
        self, ctx: JobContext, target: SwapTarget, domain: str, event: AgentEvent
    ) -> None:
        if event.run_id is None:
            return
        if event.type == "STARTED":
            await ctx.log.emit(
                RunStarted(
                    run_id=event.run_id,
                    worker=self.name,
                    product="agent",
                    site=domain,
                    url=target.url,
                    goal=target.name,
                    live=event.live,
                )
            )
        elif event.type == "STREAMING_URL" and event.streaming_url:
            await ctx.log.emit(
                RunStreamingUrl(run_id=event.run_id, streaming_url=event.streaming_url)
            )
        elif event.type == "PROGRESS" and event.purpose:
            await ctx.log.emit(RunProgress(run_id=event.run_id, purpose=event.purpose))


NO_ORIGIN = OriginEvidence(country=None, tier="none", claim_id=None)


def candidate_from_output(c: AgentMotorCandidate, run_id: str, live: bool) -> Candidate:
    """Origin starts at tier none; the CHECK stage sets it from the verified origin claim."""
    return Candidate(
        id=c.part_number or run_id,
        manufacturer=c.manufacturer,
        part_number=c.part_number,
        motor_type=c.motor_type or "unknown",
        nema_frame=c.nema_frame,
        claims=claims_from_candidate(c, run_id, live),
        origin=NO_ORIGIN,
        status="found",
        product_url=c.product_url,
    )


def claims_from_candidate(c: AgentMotorCandidate, run_id: str, live: bool) -> list[Claim]:
    """One raw claim per spec, plus one for the origin statement when the agent gave all of
    country, quote and page. Values become plain decimal strings ("4000.0", never "4e+03")."""
    via = "tinyagent" if live else "replay"
    now = datetime.now(UTC)
    candidate_id = c.part_number or run_id
    claims = [
        Claim(
            id=f"{run_id}:{i}:{spec.name}",
            candidate_id=candidate_id,
            field=spec.name,
            raw_value=format(Decimal(repr(spec.value)), "f"),
            raw_unit=spec.unit,
            quote=spec.quote,
            source=Source(
                url=spec.source_url,
                kind=_kind(spec.source_url),
                fetched_at=now,
                via=via,
                run_id=run_id,
            ),
            extracted_by="tinyagent",
        )
        for i, spec in enumerate(c.specs)
    ]
    if c.country_of_origin and c.origin_quote and c.origin_source_url:
        url = c.origin_source_url
        claims.append(
            Claim(
                id=f"{run_id}:origin",
                candidate_id=candidate_id,
                field="country_of_origin",
                raw_value=c.country_of_origin,
                raw_unit=None,
                quote=c.origin_quote,
                source=Source(url=url, kind=_kind(url), fetched_at=now, via=via, run_id=run_id),
                extracted_by="tinyagent",
            )
        )
    return claims


def _kind(url: str) -> Literal["page", "pdf"]:
    return "pdf" if urlparse(url).path.lower().endswith(".pdf") else "page"
