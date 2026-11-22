"""Job state machine (docs/design/04 section 3). Code owns the control flow; each stage is a
plain async function over the JobContext."""

import asyncio
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.agents.verifier import origin_evidence, same_page, verify_claim
from app.cad_client import CadError
from app.engineering.compliance import compliance_card
from app.engineering.ranking import RankInput, rank
from app.engineering.spec_checks import (
    BASELINE_FRAME,
    check_candidate,
    fit_badge,
    requirement,
    si_facts,
    verdict,
)
from app.orchestrator.context import Design, JobContext
from app.orchestrator.discovery import discover, plan_queries, triage
from app.orchestrator.events import (
    CheckResultPayload,
    ClaimRejected,
    ClaimVerified,
    CompliancePayload,
    DesignReady,
    ErrorPayload,
    Stage,
    StagePayload,
)
from app.orchestrator.workers import Worker
from app.schemas import BoardEntry, Claim

PIPELINE: tuple[Stage, ...] = (
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
)


async def compliance_baseline(ctx: JobContext, workers: Sequence[Worker]) -> None:
    await ctx.log.emit(CompliancePayload(card=compliance_card(ctx.robot)))


async def plan(ctx: JobContext, workers: Sequence[Worker]) -> None:
    ctx.queries = plan_queries()


async def discover_leads(ctx: JobContext, workers: Sequence[Worker]) -> None:
    ctx.leads = await discover(ctx, ctx.queries)


async def triage_leads(ctx: JobContext, workers: Sequence[Worker]) -> None:
    ctx.leads = await triage(ctx, ctx.leads)


async def extract(ctx: JobContext, workers: Sequence[Worker]) -> None:
    results = await asyncio.gather(*(w.run(ctx) for w in workers))
    ctx.candidates = [candidate for found in results for candidate in found]


# Fetch's default html keeps only the main content block; on Teknic model pages that drops the
# spec table (tests/fixtures/teknic). Claims not found in pass one get a tables-only pass.
VERIFY_PASSES: tuple[list[str] | None, ...] = (None, ["table"])


async def verify(ctx: JobContext, workers: Sequence[Worker]) -> None:
    """Re-fetch every source page fresh (ttl=0) and promote matching claims to board facts."""
    by_url: defaultdict[str, list[Claim]] = defaultdict(list)
    for candidate in ctx.candidates:
        for claim in candidate.claims:
            by_url[claim.source.url].append(claim)

    for url, claims in by_url.items():
        if claims[0].source.kind == "pdf":
            for claim in claims:
                await ctx.log.emit(ClaimRejected(claim=claim, reason="pdf verification not built"))
            continue
        pending, fetched_any = claims, False
        for selectors in VERIFY_PASSES:
            if not pending:
                break
            async with ctx.fleet.slot("fetch", ctx.budget):
                fetched = await ctx.tf.fetch(
                    [url], format="html", ttl=0, include_selectors=selectors
                )
            page = next((r for r in fetched.results if r.url == url), None)
            if page is None or not isinstance(page.text, str):
                continue
            fetched_any = True
            still_pending = []
            for claim in pending:
                checked = verify_claim(claim, page.text, "html_quote")
                if checked.verified:
                    await promote(ctx, checked)
                else:
                    still_pending.append(claim)
            pending = still_pending
        pending = await verify_on_agent_snapshot(ctx, url, pending)
        reason = (
            "quote or value not on the freshly fetched page or the agent's page snapshot"
            if fetched_any
            else "fresh fetch failed"
        )
        for claim in pending:
            await ctx.log.emit(ClaimRejected(claim=claim, reason=reason))

    checked = {fact.id: fact for fact in ctx.facts}
    ctx.candidates = [
        c.model_copy(update={"claims": [checked.get(cl.id, cl) for cl in c.claims]})
        for c in ctx.candidates
    ]


async def verify_on_agent_snapshot(ctx: JobContext, url: str, claims: list[Claim]) -> list[Claim]:
    """Last pass, for values a page fills in with JavaScript (fresh fetches never run it): the
    most recent DOM snapshot TinyFish captured of this page during the claim's own run. The
    snapshot counts only if its canonical URL is the claim's page. Returns claims still open."""
    pending = list(claims)
    for run_id in {c.source.run_id for c in claims if c.source.run_id}:
        from_run = [c for c in pending if c.source.run_id == run_id]
        async with ctx.fleet.slot("fetch", ctx.budget):
            steps = await ctx.tf.run_steps(run_id)
        for step in reversed(steps):
            async with ctx.fleet.slot("fetch", ctx.budget):
                canonical = await ctx.tf.step_canonical(run_id, step.id)
            if canonical is None or not same_page(canonical, url):
                continue
            async with ctx.fleet.slot("fetch", ctx.budget):
                snapshot = await ctx.tf.step_html(run_id, step.id)
            if snapshot is None:
                continue
            for claim in from_run:
                checked = verify_claim(claim, snapshot, "agent_dom")
                if checked.verified:
                    await promote(ctx, checked)
                    pending.remove(claim)
            break
    return pending


async def promote(ctx: JobContext, fact: Claim) -> None:
    ctx.facts.append(fact)
    await ctx.board.post(
        BoardEntry(
            job_id=ctx.job_id,
            author=BoardEntry.VERIFIER,
            kind="fact",
            subject=fact.candidate_id,
            payload=fact.model_dump(mode="json"),
            claim_id=fact.id,
            verified=True,
        )
    )
    await ctx.log.emit(ClaimVerified(claim=fact))


def design_id(job_id: str, candidate_id: str) -> str:
    """Matches the CAD worker's id pattern ^[A-Za-z0-9_-]{1,64}$."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{job_id}-{candidate_id}")[:64]


async def check(ctx: JobContext, workers: Sequence[Worker]) -> None:
    """Origin tier, bracket build (for fit numbers) and the 05 checks, per candidate."""
    req = requirement(ctx.robot.requirements)
    wheel_r_mm = ctx.robot.requirements.wheel_radius_m * 1000
    for found in ctx.candidates:
        candidate = found.model_copy(update={"origin": origin_evidence(found)})
        facts = si_facts(candidate)
        try:
            build = await ctx.cad.build(
                design_id(ctx.job_id, candidate.id),
                candidate.nema_frame,
                wheel_r_mm,
                body_len_mm=facts["body_length"][0] if "body_length" in facts else None,
                shaft_d_mm=facts["shaft_diameter"][0] if "shaft_diameter" in facts else None,
                highlight=True,
            )
        except CadError as exc:
            await ctx.log.emit(ErrorPayload(message=str(exc), stage="CHECK"))
            build = None
        fit = build.fit if build else None
        checks = check_candidate(candidate, req, fit)
        for row in checks:
            await ctx.log.emit(CheckResultPayload(check=row))
        overall = verdict(checks)
        ctx.designs.append(
            Design(
                design_id=design_id(ctx.job_id, candidate.id),
                candidate=candidate,
                checks=checks,
                verdict=overall,
                fit_badge=fit_badge(overall, candidate.nema_frame, BASELINE_FRAME, fit),
                price_usd=facts["price"][0] if "price" in facts else None,
                build=build,
            )
        )


async def rank_designs(ctx: JobContext, workers: Sequence[Worker]) -> None:
    wins = rank(
        [
            RankInput(
                candidate_id=d.candidate.id,
                verdict=d.verdict,
                price_usd=d.price_usd,
                origin_tier=d.candidate.origin.tier,
                checks=d.checks,
            )
            for d in ctx.designs
        ]
    )
    for d in ctx.designs:
        d.objectives = wins[d.candidate.id]


# Before design (HANDOFF-v3 decision 13: the demo robot's NEMA 23 bracket and its 6.35 mm wheel
# bore). Geometry for the viewer only, not a sourcing claim; the CAD worker's default body length.
BASELINE_LABEL = "Before: NEMA 23 stepper"
BASELINE_MOTOR = "NEMA 23 stepper (baseline)"


async def build(ctx: JobContext, workers: Sequence[Worker]) -> None:
    """Build the baseline robot, then publish every candidate bracket built during CHECK (fit
    numbers come from the CAD worker there). CAD trouble is reported, never fatal."""
    wheel_r_mm = ctx.robot.requirements.wheel_radius_m * 1000
    baseline_id = design_id(ctx.job_id, "before")
    try:
        before = await ctx.cad.build(baseline_id, BASELINE_FRAME, wheel_r_mm, highlight=False)
    except CadError as exc:
        await ctx.log.emit(ErrorPayload(message=str(exc), stage="BUILD"))
        return
    if before is None:  # unreachable: BASELINE_FRAME is a frame the worker models
        return
    await ctx.log.emit(
        DesignReady(
            design_id=before.design_id,
            role="baseline",
            label=BASELINE_LABEL,
            motor=BASELINE_MOTOR,
            frame=BASELINE_FRAME,
            glb_url=before.glb_url,
            step_url=before.step_url,
            fit=before.fit,
        )
    )
    for d in ctx.designs:
        if d.build is None:
            continue
        c = d.candidate
        name = " ".join(x for x in (c.manufacturer, c.part_number) if x) or c.id
        await ctx.log.emit(
            DesignReady(
                design_id=d.design_id,
                role="candidate",
                label=f"After: {name}",
                motor=name,
                frame=c.nema_frame or "",
                glb_url=d.build.glb_url,
                step_url=d.build.step_url,
                fit=d.build.fit,
                candidate_id=c.id,
                manufacturer=c.manufacturer,
                part_number=c.part_number,
                product_url=c.product_url,
                verdict=d.verdict,
                fit_badge=d.fit_badge,
                objectives=d.objectives,
                origin=c.origin,
                price_usd=d.price_usd,
            )
        )


StageFn = Callable[[JobContext, Sequence[Worker]], Awaitable[None]]
HANDLERS: dict[Stage, StageFn] = {
    "COMPLIANCE_BASELINE": compliance_baseline,
    "PLAN": plan,
    "DISCOVER": discover_leads,
    "TRIAGE": triage_leads,
    "EXTRACT": extract,
    "VERIFY": verify,
    "CHECK": check,
    "RANK": rank_designs,
    "BUILD": build,
}


# Discovery only adds leads beyond the seed targets: when it fails the job continues with the
# seeds and ends DEGRADED instead of FAILED (docs/design/04 section 3).
OPTIONAL_STAGES: frozenset[Stage] = frozenset({"PLAN", "DISCOVER", "TRIAGE"})


async def run_job(ctx: JobContext, workers: Sequence[Worker]) -> Stage:
    """Run every stage in order. An exception in an optional stage is reported and the job ends
    DEGRADED; anywhere else it ends the job FAILED. The log always closes, so SSE subscribers
    never wait on a dead job."""
    final: Stage = "FAILED"
    current: Stage = "CREATED"
    degraded = False
    try:
        for current in PIPELINE:
            await ctx.log.emit(StagePayload(stage=current))
            handler = HANDLERS.get(current)
            if handler is None:
                continue
            try:
                await handler(ctx, workers)
            except Exception as exc:
                if current not in OPTIONAL_STAGES:
                    raise
                degraded = True
                await ctx.log.emit(ErrorPayload(message=_describe(exc), stage=current))
        final = "DEGRADED" if degraded else "DONE"
    except Exception as exc:
        await ctx.log.emit(ErrorPayload(message=_describe(exc), stage=current))
    finally:
        await ctx.log.emit(StagePayload(stage=final))
        await ctx.log.close()
    return final


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


@dataclass
class Job:
    ctx: JobContext
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    task: asyncio.Task[Stage] | None = None

    @property
    def stage(self) -> Stage:
        stages = [e.data["stage"] for e in self.ctx.log.events if e.type == "stage"]
        return stages[-1] if stages else "CREATED"
