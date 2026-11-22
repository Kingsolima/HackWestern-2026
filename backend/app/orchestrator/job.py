"""Job state machine (docs/design/04 section 3). Code owns the control flow; each stage is a
plain async function over the JobContext."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.agents.verifier import verify_claim
from app.engineering.compliance import compliance_card
from app.orchestrator.cad import CadError
from app.orchestrator.context import JobContext
from app.orchestrator.events import (
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
        reason = (
            "quote or value not on the freshly fetched page"
            if fetched_any
            else "fresh fetch failed"
        )
        for claim in pending:
            await ctx.log.emit(ClaimRejected(claim=claim, reason=reason))


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


# Before/after designs for the demo. TODO(RANK): take the candidate from the ranked, checked
# motors instead of this constant once RANK exists. Values from the Teknic CPM-SDSK-2310D-RLN
# model page (length 3.34 in = 84.84 mm, shaft 0.375 in = 9.52 mm).
WHEEL_BORE_MM = 5.0  # the baseline stepper's shaft; anything else needs a hub adapter
BASELINE_DESIGN = {
    "label": "Before: NEMA 17 stepper",
    "motor": "NEMA 17 stepper (baseline)",
    "params": {"frame": "17", "body_len": 48.0, "shaft_d": 5.0, "wheel_bore": WHEEL_BORE_MM},
}
CANDIDATE_DESIGN = {
    "label": "After: Teknic NEMA 23 servo",
    "motor": "Teknic CPM-SDSK-2310D-RLN",
    "params": {
        "frame": "23",
        "body_len": 84.84,
        "shaft_d": 9.52,
        "wheel_bore": WHEEL_BORE_MM,
        "highlight": True,
    },
}


async def build(ctx: JobContext, workers: Sequence[Worker]) -> None:
    """Ask the CAD worker for the before and after robots. CAD trouble is reported, not fatal:
    the rest of the job (claims, checks) is still worth showing."""
    if ctx.cad is None:
        await ctx.log.emit(ErrorPayload(message="no CAD worker configured", stage="BUILD"))
        return
    for role, design in (("baseline", BASELINE_DESIGN), ("candidate", CANDIDATE_DESIGN)):
        suffix = "before" if role == "baseline" else "after"
        design_id = f"{ctx.job_id}-{suffix}"
        try:
            built = await ctx.cad.build(design_id, **design["params"])
        except CadError as exc:
            await ctx.log.emit(ErrorPayload(message=str(exc), stage="BUILD"))
            return
        await ctx.log.emit(
            DesignReady(
                design_id=design_id,
                role=role,
                label=design["label"],
                motor=design["motor"],
                frame=design["params"]["frame"],
                glb_url=built["glb_url"],
                step_url=built["step_url"],
                fit=built["fit"],
            )
        )


StageFn = Callable[[JobContext, Sequence[Worker]], Awaitable[None]]
HANDLERS: dict[Stage, StageFn] = {
    "COMPLIANCE_BASELINE": compliance_baseline,
    "EXTRACT": extract,
    "VERIFY": verify,
    "BUILD": build,
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
