"""Deterministic engineering checks (ARCHITECTURE §5). The LLM never does this arithmetic.

Owner 3 owns thresholds, fit-badge rules and the spec comparison table.
"""

import math

from app.engineering.nema import lookup
from app.schemas import CheckResult, CheckRow, Fit, MotorCandidate, RobotRequirements, Verdict

G = 9.81
BRACKET_THICKNESS_MM = 5.0  # TODO(owner 3): take from the CAD bracket params
CLEARANCE_MM = 5.0


def required_torque_nm(req: RobotRequirements) -> float:
    """r·m·(g·(Crr·cosθ + sinθ) + a) / (n·G·η) · SF — required torque per motor."""
    theta = math.radians(req.max_slope_deg)
    force = req.mass_kg * (G * (req.crr * math.cos(theta) + math.sin(theta)) + req.accel_mps2)
    wheel_torque = req.wheel_radius_m * force
    return wheel_torque / (req.n_drive_motors * req.gear_ratio * req.efficiency) * req.safety_factor


def top_speed_mps(rated_speed_rpm: float, req: RobotRequirements) -> float:
    """(rated_speed_rpm / G) · 2πr / 60."""
    return (rated_speed_rpm / req.gear_ratio) * 2 * math.pi * req.wheel_radius_m / 60


def run_checks(motor: MotorCandidate, req: RobotRequirements) -> CheckResult:
    sources = [u for u in (motor.product_url, motor.datasheet_url) if u]
    rows: list[CheckRow] = []

    need_t = required_torque_nm(req)
    t = motor.rated_torque_nm
    rows.append(
        CheckRow(
            check="torque",
            value=t,
            threshold=need_t,
            passed=None if t is None else t >= need_t,
            sources=sources,
        )
    )

    v = None if motor.rated_speed_rpm is None else top_speed_mps(motor.rated_speed_rpm, req)
    rows.append(
        CheckRow(
            check="speed",
            value=v,
            threshold=req.v_max_mps,
            passed=None if v is None else v >= req.v_max_mps,
            sources=sources,
        )
    )

    # TODO(owner 3): accept a driver-supported voltage range instead of exact match.
    volt = motor.voltage_v
    rows.append(
        CheckRow(
            check="voltage",
            value=volt,
            threshold=req.bus_voltage_v,
            passed=None if volt is None else math.isclose(volt, req.bus_voltage_v),
            sources=sources,
        )
    )

    frame = lookup(motor.nema_frame)
    length = motor.body_length_mm
    fit_len = None if length is None else length + BRACKET_THICKNESS_MM + CLEARANCE_MM
    fit_ok = None if fit_len is None or frame is None else fit_len <= req.envelope_mm
    rows.append(
        CheckRow(
            check="fit", value=fit_len, threshold=req.envelope_mm, passed=fit_ok, sources=sources
        )
    )

    hard = {r.check: r.passed for r in rows}
    if any(hard[c] is False for c in ("torque", "speed", "voltage")):
        verdict = Verdict.rejected
    elif all(r.passed for r in rows):
        verdict = Verdict.passed
    else:
        verdict = Verdict.review

    # TODO(owner 3): real drop_in/close rule (same frame as current motor, length delta).
    fit = Fit.drop_in if fit_ok else Fit.needs_review
    candidate = motor.part_number or "unknown"
    return CheckResult(candidate=candidate, verdict=verdict, fit=fit, rows=rows)
