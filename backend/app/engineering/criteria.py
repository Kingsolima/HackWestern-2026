"""CRITERIA (docs/BUILD-PLAN-v4.md section 5): code turns a project's facts into objectives,
thresholds and blocking lists. Every effect carries the rule and the fact that caused it, so the
UI can show why a criterion is on. No rule fires on an unknown fact."""

from app.schemas import Criteria, CriterionReason, Objective, ProjectFacts

# FAR 25.101 domestic content threshold for federal buys (the v3 pass rule): strictly above.
FEDERAL_DOMESTIC_THRESHOLD = 0.65


def derive_criteria(facts: ProjectFacts) -> Criteria:
    objectives = [Objective.performance, Objective.cost]
    reasons = [
        CriterionReason(rule="always", fact=None, text="spec checks are a hard gate"),
        CriterionReason(rule="always", fact=None, text="cost delta is part of every trade-off"),
    ]
    blocking: list = []
    duty: list[str] = []
    threshold = None
    if facts.sells_to_us_federal:
        objectives.append(Objective.us_first)
        threshold = FEDERAL_DOMESTIC_THRESHOLD
        blocking += ["dod_1260h", "fcc_covered"]
        reasons.append(
            CriterionReason(
                rule="C1",
                fact="sells_to_us_federal",
                text="sells to US federal buyers: domestic content above 65%, no DoD 1260H "
                "or FCC Covered List suppliers",
            )
        )
    if "US" in facts.deploy_countries:
        duty.append("US")
        blocking.append("uflpa")
        reasons.append(
            CriterionReason(
                rule="C2",
                fact="deploy_countries",
                text="deploys in the US: US import duty counts, no UFLPA Entity List suppliers",
            )
        )
    if "CA" in facts.deploy_countries:
        duty.append("CA")
        reasons.append(
            CriterionReason(
                rule="C3", fact="deploy_countries", text="deploys in Canada: Canadian duty counts"
            )
        )
    if facts.uptime_critical:
        objectives.append(Objective.supply_risk)
        reasons.append(
            CriterionReason(
                rule="C4",
                fact="uptime_critical",
                text="downtime is costly: lowest supply risk is an objective",
            )
        )
    if facts.need_by_days is not None:
        objectives.append(Objective.lead_time)
        reasons.append(
            CriterionReason(
                rule="C5",
                fact="need_by_days",
                text=f"parts needed within {facts.need_by_days} days: longer lead times block",
            )
        )
    if facts.budget_usd is not None:
        reasons.append(
            CriterionReason(
                rule="C6",
                fact="budget_usd",
                text=f"budget ${facts.budget_usd:,.0f}: a BOM over budget is a finding",
            )
        )
    return Criteria(
        objectives=objectives,
        domestic_threshold=threshold,
        max_lead_time_days=facts.need_by_days,
        budget_usd=facts.budget_usd,
        duty_countries=duty,
        blocking_lists=blocking,
        reasons=reasons,
    )
