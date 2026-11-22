"""The one way a claim becomes a fact: kept on the job, written to the board as the verifier,
and announced. Only call it with a claim verify_claim returned verified."""

from app.orchestrator.context import JobContext
from app.orchestrator.events import ClaimVerified
from app.schemas import BoardEntry, Claim


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
