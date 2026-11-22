import math
from datetime import UTC, datetime

import pytest

from app.api.routes import load_demo_robot
from app.engineering.spec_checks import (
    check_candidate,
    fit_badge,
    requirement,
    verdict,
)
from app.schemas import Candidate, Claim, OriginEvidence, Source

REQ = requirement(load_demo_robot().requirements)
FIT_OK = {
    "envelope_used_mm": 94.8,
    "inboard_room_mm": 100.0,
    "fit_envelope": True,
    "ground_clearance_mm": 24.4,
    "fit_ground": True,
    "params": {"min_ground_clearance": 10.0},
    "wheel_bore_mm": 6.35,
    "needs_hub_adapter": False,
}


def test_demo_requirement_matches_the_handoff():
    assert math.isclose(REQ.t_peak_nm, 0.388, abs_tol=0.0005)
    assert math.isclose(REQ.w_rpm, 159.15, abs_tol=0.01)
    assert math.isclose(REQ.t_cont_nm, 0.2626, abs_tol=0.0005)


def claim(field, value, unit, verified=True):
    return Claim(
        id=f"c-{field}",
        candidate_id="m",
        field=field,
        raw_value=value,
        raw_unit=unit,
        quote="q",
        source=Source(
            url="https://m/p", kind="page", fetched_at=datetime.now(UTC), via="tinyfetch"
        ),
        extracted_by="tinyagent",
        verified=verified,
    )


GOOD = [
    claim("continuous_torque", "60", "oz-in"),
    claim("peak_torque", "180", "oz-in"),
    claim("rated_speed", "3000", "RPM"),
    claim("supply_voltage_min", "12", "VDC"),
    claim("supply_voltage_max", "75", "VDC"),
    claim("body_length", "3.34", "in"),
    claim("shaft_diameter", "6.35", "mm"),
]


def cand(claims, motor_type="servo_integrated", frame="23"):
    return Candidate(
        id="m",
        manufacturer="M",
        part_number="P",
        motor_type=motor_type,
        nema_frame=frame,
        claims=claims,
        origin=OriginEvidence(country=None, tier="none", claim_id=None),
        status="found",
    )


def by_check(checks):
    return {c.check: c for c in checks}


def replace(field, new):
    return [new if c.field == field else c for c in GOOD]


def without(field):
    return [c for c in GOOD if c.field != field]


def test_good_servo_passes_every_check_and_is_drop_in():
    checks = check_candidate(cand(GOOD), REQ, FIT_OK)
    assert {c.verdict for c in checks} == {"pass"}
    assert verdict(checks) == "pass"
    assert fit_badge("pass", "23", "23", FIT_OK) == "drop_in"
    torque = by_check(checks)["torque_cont"]
    assert torque.claim_ids == ["c-continuous_torque"] and torque.margin > 1


def test_low_continuous_torque_fails_and_rejects():
    checks = check_candidate(
        cand(replace("continuous_torque", claim("continuous_torque", "13", "oz-in"))), REQ, FIT_OK
    )
    assert by_check(checks)["torque_cont"].verdict == "fail"
    assert verdict(checks) == "rejected"
    assert fit_badge("rejected", "23", "23", FIT_OK) is None


def test_unverified_torque_is_review_not_fail():
    weak = claim("continuous_torque", "13", "oz-in", verified=False)
    checks = check_candidate(cand(replace("continuous_torque", weak)), REQ, FIT_OK)
    assert by_check(checks)["torque_cont"].verdict == "review"
    assert verdict(checks) == "review"


def test_unknown_unit_is_review():
    checks = check_candidate(
        cand(replace("continuous_torque", claim("continuous_torque", "60", "furlong-in"))),
        REQ,
        FIT_OK,
    )
    assert by_check(checks)["torque_cont"].verdict == "review"


def test_missing_peak_uses_continuous_when_it_clears_the_peak_requirement():
    checks = check_candidate(cand(without("peak_torque")), REQ, FIT_OK)
    assert by_check(checks)["torque_peak"].verdict == "pass"
    assert by_check(checks)["torque_peak"].note == "continuous torque"


def test_missing_peak_with_low_continuous_is_review():
    claims = [
        c
        for c in replace("continuous_torque", claim("continuous_torque", "40", "oz-in"))
        if c.field != "peak_torque"
    ]
    assert by_check(check_candidate(cand(claims), REQ, FIT_OK))["torque_peak"].verdict == "review"


def test_speed_falls_back_to_max_speed_with_a_note():
    checks = check_candidate(
        cand(replace("rated_speed", claim("max_speed", "4000", "RPM"))), REQ, FIT_OK
    )
    speed = by_check(checks)["speed"]
    assert speed.verdict == "pass" and "max speed" in speed.note


def test_bus_outside_supply_range_fails():
    checks = check_candidate(
        cand(replace("supply_voltage_min", claim("supply_voltage_min", "36", "VDC"))), REQ, FIT_OK
    )
    assert by_check(checks)["voltage"].verdict == "fail"


def test_bldc_voltage_needs_driver_range():
    assert (
        by_check(check_candidate(cand(GOOD, motor_type="bldc"), REQ, FIT_OK))["voltage"].verdict
        == "review"
    )


def test_stepper_torque_and_speed_are_review():
    checks = by_check(check_candidate(cand(GOOD, motor_type="stepper"), REQ, FIT_OK))
    assert {checks[c].verdict for c in ("torque_cont", "torque_peak", "speed")} == {"review"}


def test_shaft_mismatch_needs_hub_adapter_review_and_close_is_impossible_under_review():
    fit = FIT_OK | {"needs_hub_adapter": True}
    checks = check_candidate(
        cand(replace("shaft_diameter", claim("shaft_diameter", "0.375", "in"))), REQ, fit
    )
    shaft = by_check(checks)["fit_shaft"]
    assert (shaft.verdict, shaft.note) == ("review", "needs hub adapter")
    assert fit_badge(verdict(checks), "23", "23", fit) == "needs_review"


def test_pass_on_another_frame_is_close():
    assert fit_badge("pass", "34", "23", FIT_OK) == "close"


def test_ground_and_envelope_failures_come_from_cad_numbers():
    fit = FIT_OK | {"fit_ground": False, "ground_clearance_mm": 4.0, "fit_envelope": False}
    checks = by_check(check_candidate(cand(GOOD), REQ, fit))
    assert checks["fit_ground"].verdict == "fail" and checks["fit_ground"].value == 4.0
    assert checks["fit_envelope"].verdict == "fail"


def test_unverified_body_length_makes_envelope_review():
    checks = by_check(check_candidate(cand(without("body_length")), REQ, FIT_OK))
    assert checks["fit_envelope"].verdict == "review"


@pytest.mark.parametrize("check", ["fit_envelope", "fit_ground", "fit_shaft"])
def test_no_cad_means_fit_review(check):
    assert by_check(check_candidate(cand(GOOD), REQ, None))[check].verdict == "review"


def test_gear_ratio_scales_motor_speed_and_divides_torque():
    geared = load_demo_robot().requirements.model_copy(update={"gear_ratio": 3.0})
    req = requirement(geared)
    assert math.isclose(req.w_rpm, REQ.w_rpm * 3)
    assert math.isclose(req.t_cont_nm, REQ.t_cont_nm / 3)
