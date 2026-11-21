import math

import pytest

from app.api.routes import load_demo_robot
from app.engineering.checks import required_torque_nm, run_checks, top_speed_mps
from app.engineering.compliance import compliance_card
from app.engineering.nema import lookup
from app.schemas import AgentStatus, MotorCandidate, RobotRequirements, Verdict


@pytest.fixture
def req() -> RobotRequirements:
    return RobotRequirements(
        mass_kg=10,
        wheel_radius_m=0.05,
        n_drive_motors=2,
        gear_ratio=1,
        efficiency=1,
        crr=0,
        max_slope_deg=0,
        accel_mps2=1,
        v_max_mps=0.5,
        bus_voltage_v=24,
        envelope_mm=100,
        safety_factor=1,
    )


def motor(**kw) -> MotorCandidate:
    base = dict(
        status=AgentStatus.success,
        reason="ok",
        part_number="M1",
        nema_frame="23",
        body_length_mm=56,
        rated_torque_nm=1.0,
        rated_speed_rpm=300,
        voltage_v=24,
    )
    return MotorCandidate(**(base | kw))


def test_nema_lookup():
    assert lookup("23").bolt_spacing_mm == 47.14
    assert lookup("NEMA 17").pilot_diameter_mm == 22.0
    assert lookup("42") is None


def test_required_torque_flat_ground(req):
    # r·m·a / n = 0.05·10·1 / 2
    assert math.isclose(required_torque_nm(req), 0.25)


def test_top_speed(req):
    assert math.isclose(top_speed_mps(60, req), 2 * math.pi * 0.05 / 60 * 60)


def test_pass(req):
    assert run_checks(motor(), req).verdict == Verdict.passed


def test_rejected_on_torque(req):
    assert run_checks(motor(rated_torque_nm=0.1), req).verdict == Verdict.rejected


def test_missing_data_is_review(req):
    assert run_checks(motor(body_length_mm=None), req).verdict == Verdict.review


def test_demo_compliance_counts_unknown_and_canada_as_foreign():
    card = compliance_card(load_demo_robot())
    assert card.domestic_pct < 65
    assert not card.us_final_assembly
    assert any("ndfeb" in r for r in card.supply_risks)
