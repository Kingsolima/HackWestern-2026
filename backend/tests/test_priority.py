"""Risk priority and actions (engineering/priority.py) and the concern reader's checks."""

from app.engineering.concerns import confirm_concerns
from app.engineering.criteria import derive_criteria
from app.engineering.priority import decide, priority, rank
from app.schemas import (
    Alternative,
    BomLine,
    Concern,
    Criteria,
    Dependency,
    LineRisk,
    ProjectFacts,
    Recommendation,
    RiskFactor,
)

MAGNETS = Concern(id="m", kind="material", label="rare-earth magnets", country="CN", quote="x")
NO_CHINA = Concern(id="cn", kind="country", label="parts made in China", country="CN", quote="x")


def criteria(*concerns: Concern, **facts) -> Criteria:
    return derive_criteria(ProjectFacts(**facts)).model_copy(update={"concerns": list(concerns)})


def line(**kw) -> BomLine:
    base = {"id": "motor", "domain": "actuation", "qty": 2, "part": "Drive motor"}
    return BomLine(**(base | kw))


def risk(blocked=False, **levels) -> LineRisk:
    """Supply factors by name; anything not given is unknown."""
    names = [
        "bottleneck",
        "trade",
        "restricted",
        "availability",
        *(["sources"] * ("sources" in levels)),
    ]
    factors = [
        RiskFactor(
            name=n, level=levels.get(n, "unknown"), value=levels.get(n, "unknown"), reason=""
        )
        for n in dict.fromkeys(names)
    ]
    return LineRisk(line_id="motor", factors=factors, overall="low", blocked=blocked)


def scored(ln: BomLine, rk: LineRisk, cr: Criteria, deps=()) -> LineRisk:
    return rk.model_copy(update={"priority": priority(ln, rk, cr, list(deps))})


def likely(concern="m", line_id="motor") -> Dependency:
    return Dependency(
        line_id=line_id, concern_id=concern, depends="likely", why="permanent magnets"
    )


def alt(cr: Criteria, verdict="pass", origin="US", price=100.0, deps=()) -> Alternative:
    as_line = line(id="alt", origin_country=origin, unit_price_usd=price)
    return Alternative(
        id="alt",
        line_id="motor",
        manufacturer="Acme",
        part_number="A1",
        origin_country=origin,
        unit_price_usd=price,
        verdict=verdict,
        live=False,
        risk=scored(as_line, risk(restricted="low"), cr, deps),
    )


def test_a_material_is_only_a_risk_for_the_customer_who_named_it():
    china_motor = line(origin_country="CN")
    rk = risk(bottleneck="low", restricted="low")
    indifferent = priority(china_motor, rk, criteria(), [likely()])
    assert indifferent.customer.value == 0  # nobody objected: the magnet does not score
    concerned = priority(china_motor, rk, criteria(MAGNETS), [likely()])
    assert (concerned.customer.value, concerned.customer.basis) == (2, "inferred")
    assert "inferred from the part class, not verified" in concerned.customer.reasons[0]
    assert (concerned.lo, concerned.hi, concerned.level) == (5, 5, "medium")


def test_unknown_evidence_is_unknown_never_zero():
    cr = criteria(MAGNETS)
    no_answer = priority(line(origin_country="CN"), risk(), cr, [])  # model said nothing
    assert no_answer.customer.value is None and no_answer.supply.value is None
    assert (no_answer.lo, no_answer.hi) == (3, 9)  # impact 3; two unknown scores widen the range
    assert "whether this part depends on rare-earth magnets" in no_answer.customer.missing
    # made in the US: the part is not Chinese, but where its magnets come from is not known
    us = priority(line(origin_country="US"), risk(), cr, [likely()])
    assert us.customer.value is None and "not verified" in us.customer.missing[0]
    unlikely = Dependency(line_id="motor", concern_id="m", depends="unlikely")
    assert priority(line(), risk(), cr, [unlikely]).customer.value == 0


def test_stated_conflicts_score_three_and_supply_and_impact_follow_their_rules():
    cr = criteria(NO_CHINA, MAGNETS, uptime_critical=True)
    stated = priority(line(origin_country="CN"), risk(restricted="low"), cr, [])
    assert (stated.customer.value, stated.customer.basis) == (3, "stated")
    flagged = line(origin_country="KR", stated_risk="ndfeb_magnets")
    assert priority(flagged, risk(), criteria(MAGNETS), []).customer.value == 3
    assert priority(line(), risk(availability="high"), cr, []).supply.value == 3
    assert priority(line(), risk(bottleneck="high"), cr, []).supply.value == 2
    assert priority(line(), risk(trade="medium", bottleneck="low"), cr, []).supply.value == 1
    encoder = line(domain="sensing")
    assert priority(encoder, risk(), cr, []).impact.value == 3  # 2, raised by costly downtime
    assert priority(encoder, risk(), criteria(), []).impact.value == 2
    assert priority(line(domain="structure"), risk(), cr, []).impact.value == 1
    federal = criteria(sells_to_us_federal=True)
    assert (
        priority(line(origin_country="CN"), risk(restricted="low"), federal, []).customer.value == 2
    )
    assert (
        priority(line(origin_country="US"), risk(restricted="low"), federal, []).customer.value == 0
    )


def test_actions_follow_the_rules_in_order():
    cr = criteria(NO_CHINA)
    china = line(origin_country="CN", unit_price_usd=60.0)
    current = scored(china, risk(restricted="low", bottleneck="low"), cr)
    # 1. documented conflict + an alternative that passed and has no conflict
    rec = decide(china, current, [alt(cr)])
    assert (rec.action, rec.alternative_id, rec.cost_delta_usd) == ("re_source", "alt", 80.0)
    # 2. same conflict, but the alternative's specs are not verified yet
    rec = decide(china, current, [alt(cr, verdict="review")])
    assert rec.action == "investigate" and "specs are not all verified" in rec.reason
    assert decide(china, current, [alt(cr, verdict="rejected")]).action == "investigate"
    # 2. an inferred conflict never re-sources, even with a clean passing alternative
    mc = criteria(MAGNETS)
    inferred = scored(china, risk(restricted="low", bottleneck="low"), mc, [likely()])
    rec = decide(china, inferred, [alt(mc, deps=[likely()])])
    assert rec.action == "investigate" and "inferred, so confirm it first" in rec.reason
    assert "where its rare-earth magnets come from" in rec.reason  # the US alternative's gap
    # 3. cannot tell whether it conflicts
    unknown = scored(line(), risk(restricted="low", bottleneck="low"), cr)
    assert decide(line(), unknown, []).action == "investigate"
    # 4. no supply evidence on a part the robot depends on
    blind = scored(line(), risk(), criteria())
    assert decide(line(), blind, []).action == "investigate"
    assert (
        decide(
            line(domain="structure"), scored(line(domain="structure"), risk(), criteria()), []
        ).action
        == "keep"
    )
    # 5. fine for the customer, exposed supply
    exposed = scored(line(), risk(bottleneck="high", restricted="low"), criteria())
    rec = decide(line(), exposed, [alt(criteria())])
    assert (rec.action, rec.alternative_id) == ("dual_source", "alt")
    assert decide(line(), exposed, []).action == "dual_source"
    # 6. nothing known needs action; what was not checked is said
    calm = scored(line(), risk(bottleneck="low", restricted="low"), criteria())
    rec = decide(line(), calm, [])
    assert rec.action == "keep" and "Not checked: import duty" in rec.reason


def test_rank_puts_action_first_and_highest_priority_first():
    def rec(line_id, action, lo, hi):
        return Recommendation(
            line_id=line_id,
            action=action,
            risk_before="low",
            risk_after="low",
            priority_lo=lo,
            priority_hi=hi,
            reason="",
        )

    order = rank(
        [rec("a", "keep", 8, 8), rec("b", "investigate", 3, 9), rec("c", "re_source", 6, 6)]
    )
    assert [r.line_id for r in order] == ["c", "b", "a"]


def test_concerns_are_kept_only_when_the_customer_said_them():
    avoid = "We want to avoid motors that depend on Chinese rare-earth magnets."
    bom = [line(), line(id="plate", domain="structure", part="Base plate")]
    raw = {
        "concerns": [
            {
                "id": "m",
                "kind": "material",
                "label": "rare-earth magnets",
                "country": "cn",
                "quote": "Chinese  rare-earth magnets",
            },
            {"id": "x", "kind": "supplier", "label": "Acme", "quote": "never buy from Acme"},
            {"id": "y", "kind": "country", "label": "Russia", "country": None, "quote": "avoid"},
        ],
        "dependencies": [
            {"line_id": "motor", "concern_id": "m", "depends": "likely", "why": "magnets"},
            {"line_id": "plate", "concern_id": "m", "depends": "unlikely"},
            {"line_id": "ghost", "concern_id": "m", "depends": "likely"},
            {"line_id": "motor", "concern_id": "x", "depends": "likely"},
            {"line_id": "motor", "concern_id": "m", "depends": "certainly"},
        ],
    }
    concerns, deps = confirm_concerns(raw, avoid, bom)
    assert [(c.id, c.country) for c in concerns] == [("m", "CN")]  # invented ones dropped
    assert {(d.line_id, d.depends) for d in deps} == {("motor", "likely"), ("plate", "unlikely")}
