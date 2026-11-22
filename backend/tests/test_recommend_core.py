"""Tygo's chunk B core: recommend(). These fail until it is written.

Spec: docs/BUILD-PLAN-v4.md section 5 and the docstring of app/engineering/risk.py recommend().
"""

from app.engineering.risk import recommend
from app.schemas import Alternative, BomLine, LineRisk, RiskFactor


def risk(level, blocked=False, line="x"):
    factor = RiskFactor(name="bottleneck", level=level, value=level, reason="test")
    return LineRisk(line_id=line, factors=[factor], overall=level, blocked=blocked)


def alt(id, level, price, verdict=None, blocked=False):
    return Alternative(
        id=id,
        line_id="motor",
        manufacturer=id,
        part_number=id,
        unit_price_usd=price,
        verdict=verdict,
        risk=risk(level, blocked, id),
        live=False,
    )


LINE = BomLine(id="motor", domain="actuation", qty=2, part="NEMA 23 servo", unit_price_usd=100.0)


def test_no_alternatives_keeps():
    r = recommend(LINE, risk("high"), [])
    assert (r.action, r.alternative_id, r.risk_before, r.risk_after) == (
        "keep",
        None,
        "high",
        "high",
    )
    assert r.cost_delta_usd is None and not r.blocked and r.reason


def test_cheaper_and_safer_re_sources_with_cost_delta_times_qty():
    r = recommend(LINE, risk("high"), [alt("a", "low", 90.0)])
    assert (r.action, r.alternative_id, r.cost_delta_usd) == ("re_source", "a", -20.0)
    assert (r.risk_before, r.risk_after) == ("high", "low")


def test_same_price_and_safer_re_sources():
    assert recommend(LINE, risk("medium"), [alt("a", "low", 100.0)]).action == "re_source"


def test_safer_but_pricier_dual_sources():
    r = recommend(LINE, risk("high"), [alt("a", "medium", 150.0)])
    assert (r.action, r.alternative_id, r.cost_delta_usd) == ("dual_source", "a", 100.0)


def test_unknown_price_cannot_prove_cheaper_so_it_dual_sources():
    r = recommend(LINE, risk("high"), [alt("a", "low", None)])
    assert (r.action, r.cost_delta_usd) == ("dual_source", None)


def test_unknown_current_price_also_means_unknown_delta():
    line = LINE.model_copy(update={"unit_price_usd": None})
    r = recommend(line, risk("high"), [alt("a", "low", 10.0)])
    assert (r.action, r.cost_delta_usd) == ("dual_source", None)


def test_not_safer_keeps_even_when_cheaper():
    r = recommend(LINE, risk("medium"), [alt("same", "medium", 50.0), alt("worse", "high", 1.0)])
    assert (r.action, r.alternative_id) == ("keep", None)


def test_unknown_risk_is_never_an_improvement():
    assert recommend(LINE, risk("high"), [alt("a", "unknown", 1.0)]).action == "keep"
    assert recommend(LINE, risk("unknown"), [alt("a", "low", 1.0)]).action == "keep"


def test_rejected_or_blocked_alternatives_are_not_eligible():
    alts = [alt("rej", "low", 50.0, verdict="rejected"), alt("blk", "low", 50.0, blocked=True)]
    assert recommend(LINE, risk("high"), alts).action == "keep"


def test_review_verdict_is_still_eligible():
    assert recommend(LINE, risk("high"), [alt("a", "low", 90.0, "review")]).action == "re_source"


def test_re_source_picks_lowest_risk_then_cheapest():
    alts = [alt("med_cheap", "medium", 10.0), alt("low_b", "low", 95.0), alt("low_a", "low", 80.0)]
    assert recommend(LINE, risk("high"), alts).alternative_id == "low_a"


def test_dual_source_picks_lowest_risk_then_smallest_delta_unknown_last():
    alts = [
        alt("med", "medium", 101.0),
        alt("low_unknown", "low", None),
        alt("low_pricey", "low", 300.0),
        alt("low_less", "low", 200.0),
    ]
    assert recommend(LINE, risk("high"), alts).alternative_id == "low_less"


def test_ties_break_by_id():
    alts = [alt("b", "low", 90.0), alt("a", "low", 90.0)]
    assert recommend(LINE, risk("high"), alts).alternative_id == "a"


def test_a_cheaper_dominating_option_beats_a_safer_pricier_one():
    # re_source candidates are considered before dual_source ones
    alts = [alt("safest_pricey", "low", 500.0), alt("safer_cheap", "medium", 90.0)]
    r = recommend(LINE, risk("high"), alts)
    assert (r.action, r.alternative_id) == ("re_source", "safer_cheap")


def test_blocked_current_re_sources_to_the_cheapest_eligible_even_if_riskier():
    alts = [alt("pricey_low", "low", 400.0), alt("cheap_high", "high", 120.0)]
    r = recommend(LINE, risk("high", blocked=True), alts)
    assert (r.action, r.alternative_id, r.blocked) == ("re_source", "cheap_high", True)
    assert (r.cost_delta_usd, r.risk_after) == (40.0, "high")


def test_blocked_current_prefers_known_prices():
    alts = [alt("unknown", "low", None), alt("known", "low", 900.0)]
    assert recommend(LINE, risk("low", blocked=True), alts).alternative_id == "known"


def test_blocked_with_nothing_eligible_says_so():
    r = recommend(LINE, risk("high", blocked=True), [alt("rej", "low", 1.0, verdict="rejected")])
    assert (r.action, r.alternative_id, r.blocked, r.risk_after) == ("keep", None, True, "high")
    assert "no eligible" in r.reason.lower()


def test_real_drive_motor_case():
    # Research pass 1 (data/research/demo_bom.yaml): STEPPERONLINE iSV57T-090S $77.15, China,
    # T3; Teknic CPM-SDSK-2310S-RLN $265, own page "Country of Origin USA", T1, and the
    # recorded live job's verdict "review" (shaft needs a hub adapter). Teknic is safer but
    # costs $187.85 more per motor, two motors: dual-source, not re-source.
    line = BomLine(
        id="drive_motor",
        domain="actuation",
        qty=2,
        part="NEMA 23 integrated servo",
        manufacturer="STEPPERONLINE",
        part_number="iSV57T-090S",
        unit_price_usd=77.15,
    )
    teknic = alt("teknic", "low", 265.0, verdict="review")
    r = recommend(line, risk("high"), [teknic])
    assert (r.action, r.alternative_id) == ("dual_source", "teknic")
    assert abs(r.cost_delta_usd - 375.70) < 1e-9


def test_an_alternative_that_passed_beats_a_safer_one_that_needs_review():
    alts = [
        alt("unchecked_low", "low", 90.0, "review"),
        alt("passed_medium", "medium", 90.0, "pass"),
    ]
    r = recommend(LINE, risk("high"), alts)
    assert (r.action, r.alternative_id) == ("re_source", "passed_medium")
    assert "need review" not in r.reason


def test_reasons_say_what_is_not_verified():
    # Real Stretch case: Moog SM34405D found live, no spec or price verified
    r = recommend(LINE, risk("high"), [alt("moog", "low", None, "review")])
    assert r.action == "dual_source"
    assert "price is not verified" in r.reason and "specs still need review" in r.reason
    priced = recommend(LINE, risk("high"), [alt("a", "low", 150.0, "pass")])
    assert "costs more" in priced.reason and "review" not in priced.reason
