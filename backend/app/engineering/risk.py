"""Supply risk per BOM line and the keep / dual-source / re-source decision
(docs/BUILD-PLAN-v4.md section 5). Levels are ordinal; nothing is weighted or summed."""

from pydantic import BaseModel

from app.schemas import (
    Alternative,
    Availability,
    BomLine,
    Criteria,
    Level,
    LineRisk,
    Recommendation,
    RiskFactor,
)

RANK: dict[Level, int] = {"low": 0, "medium": 1, "high": 2}
HIGH_DUTY_PCT = 25.0


def worst(levels: list[Level]) -> Level:
    known = [lv for lv in levels if lv != "unknown"]
    return max(known, key=RANK.__getitem__) if known else "unknown"


def lower(a: Level, b: Level) -> bool:
    """a is strictly lower risk than b; unknown is never lower or higher than anything."""
    return a != "unknown" and b != "unknown" and RANK[a] < RANK[b]


class RiskInputs(BaseModel):
    """Evidence for one line (or one alternative), gathered from sourced data files."""

    eligible_alternatives: int | None = None  # None for an alternative's own risk
    bottleneck: Level = "unknown"
    bottleneck_source: str | None = None
    duty_pct: float | None = None  # largest added duty into any criteria duty country
    duty_note: str = ""
    duty_source: str | None = None
    list_hits: list[str] = []


def line_risk(
    line_id: str,
    availability: Availability,
    lead_time_days: int | None,
    criteria: Criteria,
    ev: RiskInputs,
) -> LineRisk:
    factors: list[RiskFactor] = []
    if ev.eligible_alternatives is not None:
        n = ev.eligible_alternatives
        factors.append(
            RiskFactor(
                name="sources",
                level="high" if n == 0 else "medium" if n == 1 else "low",
                value=f"{n} eligible alternative{'s' if n != 1 else ''}",
                reason="fewer alternatives, fewer places to turn when the supplier fails",
            )
        )
    factors.append(
        RiskFactor(
            name="bottleneck",
            level=ev.bottleneck,
            value=ev.bottleneck,
            reason="the article's tier for this component domain",
            source_urls=[ev.bottleneck_source] if ev.bottleneck_source else [],
        )
    )
    factors.append(_trade(criteria, ev))
    hits = ev.list_hits
    factors.append(
        RiskFactor(
            name="restricted",
            level="high" if hits else "low",
            value=", ".join(hits) if hits else "no hit",
            reason="supplier named on a blocking list"
            if hits
            else "checked against " + (", ".join(criteria.blocking_lists) or "no blocking lists"),
        )
    )
    avail, over_need_by = _availability(availability, lead_time_days, criteria)
    factors.append(avail)
    return LineRisk(
        line_id=line_id,
        factors=factors,
        overall=worst([f.level for f in factors]),
        blocked=bool(hits) or availability == "out_of_stock" or over_need_by,
    )


def _trade(criteria: Criteria, ev: RiskInputs) -> RiskFactor:
    if not criteria.duty_countries or ev.duty_pct is None:
        return RiskFactor(
            name="trade",
            level="unknown",
            value="unknown",
            reason=ev.duty_note or "no duty data for this line and market",
        )
    pct = ev.duty_pct
    level: Level = "low" if pct == 0 else "high" if pct >= HIGH_DUTY_PCT else "medium"
    return RiskFactor(
        name="trade",
        level=level,
        value=f"{pct:g}% added duty",
        reason=ev.duty_note or f"import duty into {', '.join(criteria.duty_countries)}",
        source_urls=[ev.duty_source] if ev.duty_source else [],
    )


def _availability(
    availability: Availability, lead_time_days: int | None, criteria: Criteria
) -> tuple[RiskFactor, bool]:
    need_by = criteria.max_lead_time_days
    over = (
        availability == "lead_time"
        and lead_time_days is not None
        and need_by is not None
        and lead_time_days > need_by
    )
    if availability == "out_of_stock" or over:
        level: Level = "high"
    elif availability == "in_stock" or (
        availability == "lead_time"
        and lead_time_days is not None
        and (need_by is None or lead_time_days <= need_by)
    ):
        level = "low"
    elif availability == "lead_time":
        level = "medium"
    else:
        level = "unknown"
    days = f" ({lead_time_days} days)" if lead_time_days is not None else ""
    limit = f", need-by {need_by} days" if need_by is not None else ""
    return (
        RiskFactor(
            name="availability",
            level=level,
            value=f"{availability}{days}",
            reason=f"stock and lead time as the seller states them{limit}",
        ),
        over,
    )


def recommend(line: BomLine, current: LineRisk, alternatives: list[Alternative]) -> Recommendation:
    """Tygo's chunk B core. Contract (tests/test_recommend_core.py):

    Eligible alternatives: verdict is not "rejected" and alt.risk.blocked is False.
    cost_delta(alt) = (alt.unit_price_usd - line.unit_price_usd) * line.qty, or None when
    either price is None.
    1. current.blocked: re_source to the eligible alternative with the lowest known price
       (unknown prices last, then by id); blocked=True. No eligible alternative -> action
       "keep", alternative_id None, blocked=True, risk_after = current.overall, and a reason
       that says nothing eligible was found.
    2. Else, among eligible alternatives with lower(alt.risk.overall, current.overall):
       a. those with cost_delta known and <= 0 -> re_source to the lowest risk, then
          cheapest, then by id;
       b. otherwise (all costlier or unknown cost) -> dual_source with the lowest risk, then
          smallest cost_delta (unknown last), then by id.
    3. Else keep: alternative_id None, risk_after = current.overall, cost_delta None.
    risk_before is always current.overall; risk_after is the chosen alternative's overall.
    In every choice above, an alternative whose specs passed comes before one that needs review
    (or was never checked), ahead of the other keys.
    reason: plain sentences a team lead can read; they say when the alternative's specs still
    need review and when its price is not verified.
    """

    def delta(a: Alternative) -> float | None:
        if a.unit_price_usd is None or line.unit_price_usd is None:
            return None
        return (a.unit_price_usd - line.unit_price_usd) * line.qty

    def unchecked(a: Alternative) -> bool:
        return a.verdict != "pass"

    def caveat(a: Alternative) -> str:
        return " Its specs still need review." if unchecked(a) else ""

    def decide(action, a: Alternative | None, reason: str) -> Recommendation:
        return Recommendation(
            line_id=line.id,
            action=action,
            alternative_id=a.id if a else None,
            cost_delta_usd=delta(a) if a else None,
            risk_before=current.overall,
            risk_after=a.risk.overall if a else current.overall,
            blocked=current.blocked,
            reason=reason,
        )

    eligible = [a for a in alternatives if a.verdict != "rejected" and not a.risk.blocked]
    if current.blocked:
        if not eligible:
            return decide(
                "keep", None, "The current part is blocked and no eligible alternative was found."
            )
        a = min(
            eligible,
            key=lambda a: (unchecked(a), a.unit_price_usd is None, a.unit_price_usd or 0.0, a.id),
        )
        return decide(
            "re_source",
            a,
            f"The current part is blocked: move to {a.manufacturer} {a.part_number}, "
            "the cheapest eligible alternative." + caveat(a),
        )

    safer = [a for a in eligible if lower(a.risk.overall, current.overall)]
    no_dearer = [a for a in safer if (d := delta(a)) is not None and d <= 0]
    if no_dearer:
        a = min(no_dearer, key=lambda a: (unchecked(a), RANK[a.risk.overall], delta(a), a.id))
        return decide(
            "re_source",
            a,
            f"{a.manufacturer} {a.part_number} is lower risk at no extra cost." + caveat(a),
        )
    if safer:
        a = min(
            safer,
            key=lambda a: (
                unchecked(a),
                RANK[a.risk.overall],
                delta(a) is None,
                delta(a) or 0.0,
                a.id,
            ),
        )
        cost = "its price is not verified" if delta(a) is None else "it costs more"
        return decide(
            "dual_source",
            a,
            f"{a.manufacturer} {a.part_number} is lower risk but {cost}: "
            "add it as a second source." + caveat(a),
        )
    return decide("keep", None, "No eligible alternative lowers the risk.")


def risk_reduction(r: Recommendation) -> int:
    if r.risk_before == "unknown" or r.risk_after == "unknown":
        return 0
    return RANK[r.risk_before] - RANK[r.risk_after]


def rank_recommendations(recs: list[Recommendation]) -> list[Recommendation]:
    """Most risk removed first, then the cheapest change; keeps go last."""

    def key(r: Recommendation) -> tuple:
        cost = r.cost_delta_usd
        return (
            r.action == "keep",
            -risk_reduction(r),
            not r.blocked,
            cost is None,
            cost if cost is not None else 0.0,
            r.line_id,
        )

    return sorted(recs, key=key)
