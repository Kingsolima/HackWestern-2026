"""Job state machine (docs/design/04 section 3). Code owns the control flow; each stage is a
plain async function over the JobContext."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.agents.verifier import canonical_url, same_page, verify_claim
from app.engineering.compliance import compliance_card
from app.orchestrator.context import JobContext
from app.orchestrator.events import (
    ClaimRejected,
    ClaimVerified,
    CompliancePayload,
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


async def extract(ctx: JobContext, workers: Sequence[Worker]) -> None:
    results = await asyncio.gather(*(w.run(ctx) for w in workers))
    ctx.raw_claims = [claim for claims in results for claim in claims]


# Fetch's default html keeps only the main content block; on Teknic model pages that drops the
# spec table (tests/fixtures/teknic). Claims not found in pass one get a tables-only pass.
VERIFY_PASSES: tuple[list[str] | None, ...] = (None, ["table"])


async def verify(ctx: JobContext, workers: Sequence[Worker]) -> None:
    """Re-fetch every source page fresh (ttl=0) and promote matching claims to board facts."""
    by_url: defaultdict[str, list[Claim]] = defaultdict(list)
    for claim in ctx.raw_claims:
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
                snapshot = await ctx.tf.step_html(run_id, step.id)
            canonical = canonical_url(snapshot) if snapshot else None
            if canonical is None or not same_page(canonical, url):
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


StageFn = Callable[[JobContext, Sequence[Worker]], Awaitable[None]]
HANDLERS: dict[Stage, StageFn] = {
    "COMPLIANCE_BASELINE": compliance_baseline,
    "EXTRACT": extract,
    "VERIFY": verify,
}


async def run_job(ctx: JobContext, workers: Sequence[Worker]) -> Stage:
    """Run every stage in order. Any exception ends the job FAILED with an `error` event; the
    log always closes, so SSE subscribers never wait on a dead job."""
    final: Stage = "FAILED"
    current: Stage = "CREATED"
    try:
        for current in PIPELINE:
            await ctx.log.emit(StagePayload(stage=current))
            handler = HANDLERS.get(current)
            if handler is not None:
                await handler(ctx, workers)
        final = "DONE"
    except Exception as exc:
        await ctx.log.emit(ErrorPayload(message=f"{type(exc).__name__}: {exc}", stage=current))
    finally:
        await ctx.log.emit(StagePayload(stage=final))
        await ctx.log.close()
    return final


@dataclass
class Job:
    ctx: JobContext
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    task: asyncio.Task[Stage] | None = None

    @property
    def stage(self) -> Stage:
        stages = [e.data["stage"] for e in self.ctx.log.events if e.type == "stage"]
        return stages[-1] if stages else "CREATED"
