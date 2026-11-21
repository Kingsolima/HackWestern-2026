"""Job state machine (docs/design/04 section 3). Code owns the control flow; each stage is a
plain async function over the JobContext."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.agents.verifier import verify_claim
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
        async with ctx.fleet.slot("fetch", ctx.budget):
            fetched = await ctx.tf.fetch([url], format="html", ttl=0)
        page = next((r for r in fetched.results if r.url == url), None)
        if page is None or not isinstance(page.text, str):
            for claim in claims:
                await ctx.log.emit(ClaimRejected(claim=claim, reason="fresh fetch failed"))
            continue
        for claim in claims:
            checked = verify_claim(claim, page.text, "html_quote")
            if not checked.verified:
                reason = "quote or value not on the freshly fetched page"
                await ctx.log.emit(ClaimRejected(claim=checked, reason=reason))
                continue
            ctx.facts.append(checked)
            await ctx.board.post(
                BoardEntry(
                    job_id=ctx.job_id,
                    author=BoardEntry.VERIFIER,
                    kind="fact",
                    subject=checked.candidate_id,
                    payload=checked.model_dump(mode="json"),
                    claim_id=checked.id,
                    verified=True,
                )
            )
            await ctx.log.emit(ClaimVerified(claim=checked))


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
