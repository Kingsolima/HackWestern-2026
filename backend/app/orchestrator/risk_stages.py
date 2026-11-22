"""RISK_BASELINE, ALTERNATIVES and RECOMMEND (docs/BUILD-PLAN-v4.md sections 3 and 5). No-ops on
v3 jobs that have no project."""

from collections.abc import Sequence

from app.engineering.risk import (
    line_risk,
    rank_recommendations,
    recommend,
)
from app.engineering.risk_data import inputs_for
from app.orchestrator.context import JobContext
from app.orchestrator.events import AlternativePayload, RecommendationPayload, RiskLinePayload
from app.schemas import Alternative, BomLine, Recommendation


def _deep(ctx: JobContext) -> BomLine:
    assert ctx.project is not None
    return next(line for line in ctx.project.bom if line.id == ctx.project.deep_line)


async def risk_baseline(ctx: JobContext, workers: Sequence[object]) -> None:
    if ctx.project is None or ctx.criteria is None:
        return
    for line in ctx.project.bom:
        risk = line_risk(
            line.id,
            line.availability,
            line.lead_time_days,
            ctx.criteria,
            inputs_for(line, ctx.criteria),
        )
        ctx.line_risks[line.id] = risk
        await ctx.log.emit(RiskLinePayload(line=line, risk=risk))


async def alternatives(ctx: JobContext, workers: Sequence[object]) -> None:
    """Every checked candidate for the deep line becomes an Alternative with its own risk; the
    deep line's risk is then re-sent with its sources factor."""
    if ctx.project is None or ctx.criteria is None:
        return
    deep = _deep(ctx)
    for d in ctx.designs:
        c = d.candidate
        as_line = deep.model_copy(
            update={
                "id": c.id,
                "manufacturer": c.manufacturer,
                "part_number": c.part_number,
                "origin_country": c.origin.country,
                "origin_tier": c.origin.tier,
                "unit_price_usd": d.price_usd,
                "availability": "unknown",
                "lead_time_days": None,
                "illustrative": False,
            }
        )
        alt = Alternative(
            id=c.id,
            line_id=deep.id,
            manufacturer=c.manufacturer or "unknown",
            part_number=c.part_number or "unknown",
            product_url=c.product_url,
            origin_country=c.origin.country,
            origin_tier=c.origin.tier,
            unit_price_usd=d.price_usd,
            verdict=d.verdict,
            risk=line_risk(c.id, "unknown", None, ctx.criteria, inputs_for(as_line, ctx.criteria)),
            live=any(claim.source.via != "replay" for claim in c.claims),
        )
        ctx.alternatives.append(alt)
        await ctx.log.emit(AlternativePayload(alternative=alt))
    eligible = sum(1 for a in ctx.alternatives if a.verdict != "rejected" and not a.risk.blocked)
    risk = line_risk(
        deep.id,
        deep.availability,
        deep.lead_time_days,
        ctx.criteria,
        inputs_for(deep, ctx.criteria, eligible_alternatives=eligible),
    )
    ctx.line_risks[deep.id] = risk
    await ctx.log.emit(RiskLinePayload(line=deep, risk=risk))


async def recommend_lines(ctx: JobContext, workers: Sequence[object]) -> None:
    if ctx.project is None or not ctx.line_risks:
        return
    recs: list[Recommendation] = []
    for line in ctx.project.bom:
        current = ctx.line_risks[line.id]
        if line.id == ctx.project.deep_line:
            recs.append(recommend(line, current, ctx.alternatives))
        else:
            recs.append(
                Recommendation(
                    line_id=line.id,
                    action="keep",
                    risk_before=current.overall,
                    risk_after=current.overall,
                    blocked=current.blocked,
                    reason="Alternatives were not searched for this line in this run.",
                )
            )
    for n, rec in enumerate(rank_recommendations(recs), start=1):
        await ctx.log.emit(RecommendationPayload(rank=n, recommendation=rec))
