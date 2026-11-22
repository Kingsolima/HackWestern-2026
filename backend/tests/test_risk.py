import pytest

from app.engineering.risk import (
    RiskInputs,
    line_risk,
    lower,
    rank_recommendations,
    risk_reduction,
    worst,
)
from app.schemas import Criteria, Objective, Recommendation

CLUB = Criteria(objectives=[Objective.performance], duty_countries=["CA"], max_lead_time_days=21)


def factors(risk):
    return {f.name: f.level for f in risk.factors}


def test_worst_ignores_unknown_unless_everything_is_unknown():
    assert worst(["low", "unknown", "medium"]) == "medium"
    assert worst(["unknown", "unknown"]) == "unknown"
    assert worst([]) == "unknown"


def test_unknown_is_never_lower():
    assert lower("low", "high") and not lower("high", "low") and not lower("low", "low")
    assert not lower("unknown", "high") and not lower("low", "unknown")


@pytest.mark.parametrize(("n", "level"), [(0, "high"), (1, "medium"), (2, "low"), (5, "low")])
def test_sources_level(n, level):
    r = line_risk("l", "in_stock", None, CLUB, RiskInputs(eligible_alternatives=n))
    assert factors(r)["sources"] == level


def test_an_alternatives_own_risk_has_no_sources_factor():
    assert "sources" not in factors(line_risk("a", "in_stock", None, CLUB, RiskInputs()))


@pytest.mark.parametrize(
    ("pct", "level"), [(0, "low"), (4, "medium"), (24.9, "medium"), (25, "high"), (29, "high")]
)
def test_trade_level(pct, level):
    assert (
        factors(line_risk("l", "in_stock", None, CLUB, RiskInputs(duty_pct=pct)))["trade"] == level
    )


def test_trade_is_unknown_without_data_or_without_a_market():
    assert factors(line_risk("l", "in_stock", None, CLUB, RiskInputs()))["trade"] == "unknown"
    no_market = CLUB.model_copy(update={"duty_countries": []})
    r = line_risk("l", "in_stock", None, no_market, RiskInputs(duty_pct=25))
    assert factors(r)["trade"] == "unknown"


def test_list_hit_is_high_and_blocks():
    r = line_risk("l", "in_stock", None, CLUB, RiskInputs(list_hits=["uflpa: Example Co"]))
    assert factors(r)["restricted"] == "high" and r.blocked and r.overall == "high"


@pytest.mark.parametrize(
    ("avail", "days", "level", "blocked"),
    [
        ("in_stock", None, "low", False),
        ("lead_time", 21, "low", False),
        ("lead_time", 22, "high", True),
        ("lead_time", None, "medium", False),
        ("out_of_stock", None, "high", True),
        ("unknown", None, "unknown", False),
    ],
)
def test_availability_against_need_by(avail, days, level, blocked):
    r = line_risk("l", avail, days, CLUB, RiskInputs())
    assert factors(r)["availability"] == level and r.blocked is blocked


def test_long_lead_time_without_a_need_by_is_low_and_not_blocked():
    open_ended = CLUB.model_copy(update={"max_lead_time_days": None})
    r = line_risk("l", "lead_time", 90, open_ended, RiskInputs())
    assert factors(r)["availability"] == "low" and not r.blocked


def test_overall_is_the_worst_known_factor():
    r = line_risk(
        "l",
        "in_stock",
        None,
        CLUB,
        RiskInputs(eligible_alternatives=1, bottleneck="low", duty_pct=0),
    )
    assert r.overall == "medium"


def rec(line, action, before, after, cost=None, blocked=False):
    return Recommendation(
        line_id=line,
        action=action,
        risk_before=before,
        risk_after=after,
        cost_delta_usd=cost,
        blocked=blocked,
        reason="",
    )


def test_ranking_most_risk_removed_then_cheapest_keeps_last():
    recs = [
        rec("keep", "keep", "low", "low"),
        rec("one_level_cheap", "re_source", "medium", "low", cost=-10),
        rec("two_levels_pricey", "dual_source", "high", "low", cost=500),
        rec("one_level_unknown_cost", "dual_source", "high", "medium"),
        rec("one_level_pricey", "dual_source", "medium", "low", cost=50),
        rec("blocked", "re_source", "high", "medium", cost=100, blocked=True),
    ]
    assert [r.line_id for r in rank_recommendations(recs)] == [
        "two_levels_pricey",
        "blocked",
        "one_level_cheap",
        "one_level_pricey",
        "one_level_unknown_cost",
        "keep",
    ]
    assert risk_reduction(rec("x", "keep", "unknown", "low")) == 0


def test_a_blocked_line_moved_to_a_riskier_part_still_ranks_above_keeps():
    recs = [
        rec("keep", "keep", "low", "low"),
        rec("forced", "re_source", "low", "high", blocked=True),
    ]
    assert [r.line_id for r in rank_recommendations(recs)] == ["forced", "keep"]
