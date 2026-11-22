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

import httpx
from pydantic import ValidationError

from app.agents.targets import GENERIC_GOAL, MOTOR_SCHEMA, SWAP_TARGETS, SwapTarget
from app.agents.triage import Lead
from app.agents.verifier import classify_outcome
from app.engineering.requirements import requirement_for
from app.orchestrator.context import JobContext
from app.orchestrator.discovery import TRIAGE_CHARS, domain_of
from app.orchestrator.events import RunFinished, RunProgress, RunStarted, RunStreamingUrl
from app.schemas import (
    AgentMotorCandidate,
    AgentRunResult,
    Candidate,
    Claim,
    ExtractedBy,
    OriginEvidence,
    Outcome,
    Source,
    Via,
)
from app.tfclient.client import AgentEvent, run_result
from app.tfclient.recorder import ReplayMiss


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


MAX_AGENT_LEADS = 2

EXTRACT_PROMPT = """\
You read one web page and fill the JSON schema for ONE NEMA 23 motor described on it. Use only
this page's text. Rules: value = the number exactly as written, unit = the unit exactly as
written, never convert; quote = the label and value exactly as they appear in the text,
character for character, adding no colons or words; null (or omit a spec) when not stated;
never guess. "Designed in" or a headquarters address is not a manufacturing statement: leave
origin fields null then. status: "success" if specs were found, "not_found" if the page has no
such motor, "incomplete" if some are missing (say which in reason).

Page URL: {url}

Page text:
{text}
"""


def pin_to_page(raw: object, url: str) -> object:
    """Flash read only this page, so every spec comes from it; fill what the model left null
    before validation. Anything else malformed still fails validation."""
    if not isinstance(raw, dict):
        return raw
    specs = raw.get("specs")
    if isinstance(specs, list):
        specs = [{**sp, "source_url": url} if isinstance(sp, dict) else sp for sp in specs]
    return {**raw, "reason": raw.get("reason") or "", "specs": specs if specs is not None else []}


class SwapWorker:
    """Hunts US-made replacements for the drive motor. Seed targets and discovered pages that
    need clicking get one TinyAgent run each (one stealth + US-proxy retry when blocked, docs/
    design/04 section 5); discovered pages that triage found readable are extracted by Gemini
    from the fetched text, with no agent run."""

    name = "swap:drive_motor"

    def __init__(self, targets: Sequence[SwapTarget] = SWAP_TARGETS) -> None:
        self.targets = targets

    async def run(self, ctx: JobContext) -> list[Candidate]:
        seed_domains = {domain_of(t.url) for t in self.targets}
        fresh = [lead for lead in ctx.leads if lead.domain not in seed_domains]
        clicks = [lead for lead in fresh if lead.route == "needs_interaction"][:MAX_AGENT_LEADS]
        targets = [
            *self.targets,
            *(SwapTarget(name=lead.domain, url=lead.url, goal=GENERIC_GOAL) for lead in clicks),
        ]
        readable = [lead for lead in fresh if lead.route == "readable"]
        results = await asyncio.gather(
            *(self._target(ctx, t) for t in targets),
            *(self._extract(ctx, lead) for lead in readable),
        )
        return [candidate for found in results for candidate in found]

    async def _extract(self, ctx: JobContext, lead: Lead) -> list[Candidate]:
        run_id = f"{ctx.job_id}:extract:{lead.domain}:{abs(hash(lead.url)) % 10**8}"
        await ctx.log.emit(
            RunStarted(
                run_id=run_id,
                worker=self.name,
                product="gemini",
                site=lead.domain,
                url=lead.url,
                goal="Read specs from the fetched page text",
                live=ctx.mode != "replay",
            )
        )
        prompt = EXTRACT_PROMPT.format(url=lead.url, text=(lead.text or "")[:TRIAGE_CHARS])
        outcome: Outcome = "success"
        reason = ""
        output = None
        try:
            async with ctx.fleet.slot("gemini", ctx.budget):
                raw = await ctx.gemini.extract_json(prompt, MOTOR_SCHEMA, enforce_schema=False)
            output = AgentMotorCandidate.model_validate(pin_to_page(raw, lead.url))
            reason = output.reason
            if output.status != "success":
                outcome = output.status
        except (httpx.HTTPError, ReplayMiss, ValidationError, ValueError) as exc:
            outcome, reason = "error", f"{type(exc).__name__}: {exc}"[:300]
        await ctx.log.emit(
            RunFinished(run_id=run_id, outcome=outcome, reason=reason, duration_s=0, live=False)
        )
        if output is None or outcome != "success":
            return []
        # The model saw only this page, so every value and the origin quote come from it.
        pinned = output.model_copy(
            update={
                "specs": [sp.model_copy(update={"source_url": lead.url}) for sp in output.specs],
                "origin_source_url": lead.url if output.origin_quote else None,
                "product_url": lead.url,
            }
        )
        return [candidate_from_output(pinned, run_id, live=True, extracted_by="gemini_text")]

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
        req = requirement_for(ctx.robot, ctx.project)
        frame = ctx.project.deep_frame if ctx.project else "23"
        goal = target.goal_for(req.t_cont_nm, req.t_peak_nm, req.v_bus, frame)
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


def candidate_from_output(
    c: AgentMotorCandidate,
    run_id: str,
    live: bool,
    extracted_by: ExtractedBy = "tinyagent",
) -> Candidate:
    """Origin starts at tier none; the CHECK stage sets it from the verified origin claim."""
    return Candidate(
        id=c.part_number or run_id,
        manufacturer=c.manufacturer,
        part_number=c.part_number,
        motor_type=c.motor_type or "unknown",
        nema_frame=c.nema_frame,
        claims=claims_from_candidate(c, run_id, live, extracted_by),
        origin=NO_ORIGIN,
        status="found",
        product_url=c.product_url,
    )


def claims_from_candidate(
    c: AgentMotorCandidate,
    run_id: str,
    live: bool,
    extracted_by: ExtractedBy = "tinyagent",
) -> list[Claim]:
    """One raw claim per spec, plus one for the origin statement when the agent gave all of
    country, quote and page. Values become plain decimal strings ("4000.0", never "4e+03")."""
    via: Via = (
        "replay" if not live else ("tinyagent" if extracted_by == "tinyagent" else "tinyfetch")
    )
    run = run_id if extracted_by == "tinyagent" else None
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
                run_id=run,
            ),
            extracted_by=extracted_by,
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
                source=Source(url=url, kind=_kind(url), fetched_at=now, via=via, run_id=run),
                extracted_by=extracted_by,
            )
        )
    return claims


def _kind(url: str) -> Literal["page", "pdf"]:
    return "pdf" if urlparse(url).path.lower().endswith(".pdf") else "page"
