import math

import pytest

from app.engineering.arm import arm_requirement, joint_torques_nm
from app.engineering.criteria import FEDERAL_DOMESTIC_THRESHOLD, derive_criteria
from app.schemas import ArmLink, ArmParams, Objective, ProjectFacts


def test_unknown_facts_fire_no_rule():
    c = derive_criteria(ProjectFacts())
    assert c.objectives == [Objective.performance, Objective.cost]
    assert c.domestic_threshold is None and c.blocking_lists == [] and c.duty_countries == []
    assert {r.rule_id for r in c.reasons} == {"always"}


def test_federal_seller_gets_domestic_threshold_and_defence_lists():
    c = derive_criteria(ProjectFacts(sells_to_us_federal=True))
    assert Objective.us_first in c.objectives
    assert c.domestic_threshold == FEDERAL_DOMESTIC_THRESHOLD == 0.65
    assert set(c.blocking_lists) == {"dod_1260h", "fcc_covered"}


def test_false_is_not_unknown_but_fires_nothing_either():
    c = derive_criteria(ProjectFacts(sells_to_us_federal=False, uptime_critical=False))
    assert c.objectives == [Objective.performance, Objective.cost]


def test_stretch_like_facts():
    c = derive_criteria(ProjectFacts(deploy_countries=["US", "CA"], uptime_critical=True))
    assert c.objectives == [Objective.performance, Objective.cost, Objective.supply_risk]
    assert c.duty_countries == ["US", "CA"] and c.blocking_lists == ["uflpa"]
    assert [r.rule_id for r in c.reasons][2:] == ["C2", "C3", "C4"]


def test_club_like_facts():
    c = derive_criteria(ProjectFacts(deploy_countries=["CA"], budget_usd=2500, need_by_days=21))
    assert Objective.lead_time in c.objectives and c.max_lead_time_days == 21
    assert c.budget_usd == 2500 and c.duty_countries == ["CA"] and c.blocking_lists == []
    assert any(r.rule_id == "C6" and "$2,500" in r.text for r in c.reasons)


def test_need_by_zero_days_still_counts():
    c = derive_criteria(ProjectFacts(need_by_days=0))
    assert c.max_lead_time_days == 0 and Objective.lead_time in c.objectives


def test_other_deploy_countries_bring_no_duty_rule():
    c = derive_criteria(ProjectFacts(deploy_countries=["DE"]))
    assert c.duty_countries == [] and c.blocking_lists == []


ARM = ArmParams(
    joint="J2",
    payload_kg=2.0,
    reach_m=0.5,
    links=[
        ArmLink(name="upper", mass_kg=1.0, com_m=0.2),
        ArmLink(name="fore", mass_kg=0.5, com_m=0.4),
    ],
    gear_ratio=50.0,
    efficiency=0.8,
    omega_max_dps=90.0,
    t_accel_s=0.5,
    safety_factor=1.5,
    bus_voltage_v=24.0,
)


def test_joint_torques_by_hand():
    hold, peak = joint_torques_nm(ARM)
    # 9.81 * (2*0.5 + 1*0.2 + 0.5*0.4) = 9.81 * 1.4
    assert hold == pytest.approx(13.734)
    # J = 2*0.25 + 1*0.04 + 0.5*0.16 = 0.62; alpha = (pi/2)/0.5 = pi
    assert peak == pytest.approx(13.734 + 0.62 * math.pi)


def test_motor_side_requirement_divides_by_gearbox_and_adds_safety_factor():
    r = arm_requirement(ARM)
    assert r.t_cont_nm == pytest.approx(13.734 * 1.5 / 40)
    assert r.t_peak_nm == pytest.approx((13.734 + 0.62 * math.pi) * 1.5 / 40)
    assert r.w_rpm == pytest.approx(90 / 360 * 60 * 50)  # 750 rpm at the motor
    assert r.v_bus == 24.0


def test_heavier_payload_or_longer_reach_never_lowers_the_requirement():
    base = arm_requirement(ARM)
    for change in ({"payload_kg": 3.0}, {"reach_m": 0.6}):
        r = arm_requirement(ARM.model_copy(update=change))
        assert r.t_cont_nm > base.t_cont_nm and r.t_peak_nm > base.t_peak_nm
