"""RISK_BASELINE, ALTERNATIVES and RECOMMEND (docs/BUILD-PLAN-v4.md sections 3 and 5). No-ops on
v3 jobs that have no project."""

from collections.abc import Sequence

from app.engineering.priority import decide, priority, rank
from app.engineering.risk import line_risk
from app.engineering.risk_data import inputs_for
from app.orchestrator.context import JobContext
from app.orchestrator.events import AlternativePayload, RecommendationPayload, RiskLinePayload
from app.schemas import Alternative, BomLine, LineRisk


def _scored(ctx: JobContext, line: BomLine, risk: LineRisk, deps_of: str) -> LineRisk:
    """Add the risk priority. An alternative is scored with its own origin and maker, and with
    the inferred dependencies of the line it would replace (same class of part)."""
    assert ctx.criteria is not None
    deps = [d for d in ctx.dependencies if d.line_id == deps_of]
    return risk.model_copy(update={"priority": priority(line, risk, ctx.criteria, deps)})


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
        risk = _scored(ctx, line, risk, line.id)
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
                "stated_risk": None,
            }
        )
        alt_risk = line_risk(c.id, "unknown", None, ctx.criteria, inputs_for(as_line, ctx.criteria))
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
            risk=_scored(ctx, as_line, alt_risk, deep.id),
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
    risk = _scored(ctx, deep, risk, deep.id)
    ctx.line_risks[deep.id] = risk
    await ctx.log.emit(RiskLinePayload(line=deep, risk=risk))


async def recommend_lines(ctx: JobContext, workers: Sequence[object]) -> None:
    """One action per part from engineering/priority.py. Only the deep line has alternatives;
    the other lines are decided on their own evidence."""
    if ctx.project is None or not ctx.line_risks:
        return
    recs = [
        decide(
            line,
            ctx.line_risks[line.id],
            ctx.alternatives if line.id == ctx.project.deep_line else [],
        )
        for line in ctx.project.bom
    ]
    for n, rec in enumerate(rank(recs), start=1):
        await ctx.log.emit(RecommendationPayload(rank=n, recommendation=rec))
