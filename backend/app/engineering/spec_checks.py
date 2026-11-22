"""Engineering checks v3 (docs/design/05). Pure functions over verified claims.

An unverified or missing input never fails a candidate; it makes the check Review. The legacy
checks.py stays behind POST /api/checks until the frontend moves to these.
"""

import math
from typing import Any, Literal

from pydantic import BaseModel

from app.engineering.units import to_si
from app.schemas import Candidate, Claim, RobotRequirements

G = 9.81
# Demo robot baseline motor (HANDOFF-v3 decision 13): NEMA 23 bracket, 6.35 mm wheel bore.
BASELINE_FRAME = "23"

CheckName = Literal[
    "torque_cont", "torque_peak", "speed", "voltage", "fit_envelope", "fit_ground", "fit_shaft"
]
CheckVerdict = Literal["pass", "fail", "review"]
Verdict = Literal["pass", "review", "rejected"]
FitBadge = Literal["drop_in", "close", "needs_review"]


class Requirement(BaseModel):
    t_cont_nm: float
    t_peak_nm: float
    w_rpm: float
    v_bus: float


class SpecCheck(BaseModel):
    candidate_id: str
    check: CheckName
    verdict: CheckVerdict
    value: float | None
    threshold: float | None
    unit: str
    margin: float | None
    claim_ids: list[str]
    note: str


def requirement(r: RobotRequirements) -> Requirement:
    """05 section 2: continuous and peak torque per motor, wheel speed at top speed."""
    theta = math.radians(r.max_slope_deg)
    f_cont = r.mass_kg * G * (r.crr * math.cos(theta) + math.sin(theta))
    f_peak = f_cont + r.mass_kg * r.accel_mps2
    per_motor = r.wheel_radius_m / (r.n_drive_motors * r.gear_ratio * r.efficiency)
    return Requirement(
        t_cont_nm=f_cont * per_motor * r.safety_factor,
        t_peak_nm=f_peak * per_motor * r.safety_factor,
        w_rpm=r.v_max_mps / (2 * math.pi * r.wheel_radius_m) * 60 * r.gear_ratio,
        v_bus=r.bus_voltage_v,
    )


def si_facts(candidate: Candidate) -> dict[str, tuple[float, Claim]]:
    """First verified, unit-convertible claim per field, in SI."""
    facts: dict[str, tuple[float, Claim]] = {}
    for claim in candidate.claims:
        if not claim.verified or claim.field in facts:
            continue
        try:
            raw = float(claim.raw_value)
        except ValueError:
            continue
        converted = to_si(raw, claim.raw_unit)
        if converted is not None:
            facts[claim.field] = (converted[0], claim)
    return facts


def _row(
    c: Candidate,
    check: CheckName,
    value: float | None,
    threshold: float | None,
    unit: str,
    claims: list[Claim],
    note: str = "",
    verdict: CheckVerdict | None = None,
) -> SpecCheck:
    if verdict is None:
        if value is None or threshold is None:
            verdict = "review"
        else:
            verdict = "pass" if value >= threshold else "fail"
    margin = value / threshold if value is not None and threshold else None
    return SpecCheck(
        candidate_id=c.id,
        check=check,
        verdict=verdict,
        value=value,
        threshold=threshold,
        unit=unit,
        margin=round(margin, 3) if margin is not None else None,
        claim_ids=[cl.id for cl in claims],
        note=note,
    )


def _torque(c: Candidate, req: Requirement, f: dict[str, tuple[float, Claim]]) -> list[SpecCheck]:
    if c.motor_type == "stepper":
        note = "stepper: holding torque only; torque at speed is not checked yet"
        return [
            _row(c, "torque_cont", None, req.t_cont_nm, "N·m", [], note),
            _row(c, "torque_peak", None, req.t_peak_nm, "N·m", [], note),
        ]
    cont = f.get("continuous_torque")
    peak = f.get("peak_torque")
    rows = [
        _row(
            c,
            "torque_cont",
            cont[0] if cont else None,
            req.t_cont_nm,
            "N·m",
            [cont[1]] if cont else [],
            "" if cont else "no verified continuous torque",
        )
    ]
    if peak:
        rows.append(_row(c, "torque_peak", peak[0], req.t_peak_nm, "N·m", [peak[1]]))
    elif cont and cont[0] >= req.t_peak_nm:
        rows.append(
            _row(c, "torque_peak", cont[0], req.t_peak_nm, "N·m", [cont[1]], "continuous torque")
        )
    else:
        value = cont[0] if cont else None
        note = "no verified peak torque"
        rows.append(
            _row(
                c,
                "torque_peak",
                value,
                req.t_peak_nm,
                "N·m",
                [cont[1]] if cont else [],
                note,
                verdict="review",
            )
        )
    return rows


def _speed(c: Candidate, req: Requirement, f: dict[str, tuple[float, Claim]]) -> SpecCheck:
    if c.motor_type == "stepper":
        return _row(c, "speed", None, req.w_rpm, "rpm", [], "stepper: no rated speed")
    if rated := f.get("rated_speed"):
        return _row(c, "speed", rated[0], req.w_rpm, "rpm", [rated[1]])
    if top := f.get("max_speed"):
        return _row(c, "speed", top[0], req.w_rpm, "rpm", [top[1]], "max speed; no rated speed")
    return _row(c, "speed", None, req.w_rpm, "rpm", [], "no verified speed")


def _voltage(c: Candidate, req: Requirement, f: dict[str, tuple[float, Claim]]) -> SpecCheck:
    if c.motor_type != "servo_integrated":
        note = "winding/rated voltage needs the driver's range, not in the robot spec yet"
        return _row(c, "voltage", None, req.v_bus, "V", [], note)
    low, high = f.get("supply_voltage_min"), f.get("supply_voltage_max")
    if not (low and high):
        return _row(c, "voltage", None, req.v_bus, "V", [], "no verified supply voltage range")
    inside = low[0] <= req.v_bus <= high[0]
    note = f"supply range {low[0]:g}-{high[0]:g} V"
    result: CheckVerdict = "pass" if inside else "fail"
    return _row(c, "voltage", req.v_bus, None, "V", [low[1], high[1]], note, verdict=result)


def _fit(
    c: Candidate, f: dict[str, tuple[float, Claim]], fit: dict[str, Any] | None
) -> list[SpecCheck]:
    if fit is None:
        return [
            _row(c, name, None, None, "mm", [], "CAD worker unavailable")
            for name in ("fit_envelope", "fit_ground", "fit_shaft")
        ]
    length, shaft = f.get("body_length"), f.get("shaft_diameter")
    frame_note = "frame as reported by the agent"
    if length:
        envelope_verdict: CheckVerdict = "pass" if fit["fit_envelope"] else "fail"
    else:
        envelope_verdict = "review"
    envelope = _row(
        c,
        "fit_envelope",
        fit["envelope_used_mm"],
        fit["inboard_room_mm"],
        "mm",
        [length[1]] if length else [],
        "" if length else "body length not verified",
        verdict=envelope_verdict,
    )
    ground = _row(
        c,
        "fit_ground",
        fit["ground_clearance_mm"],
        fit["params"]["min_ground_clearance"],
        "mm",
        [],
        frame_note,
        verdict="pass" if fit["fit_ground"] else "fail",
    )
    if not shaft:
        shaft_row = _row(c, "fit_shaft", None, fit["wheel_bore_mm"], "mm", [], "shaft not verified")
    else:
        adapter = fit["needs_hub_adapter"]
        shaft_row = _row(
            c,
            "fit_shaft",
            shaft[0],
            fit["wheel_bore_mm"],
            "mm",
            [shaft[1]],
            "needs hub adapter" if adapter else "",
            verdict="review" if adapter else "pass",
        )
    return [envelope, ground, shaft_row]


def check_candidate(c: Candidate, req: Requirement, fit: dict[str, Any] | None) -> list[SpecCheck]:
    f = si_facts(c)
    return [*_torque(c, req, f), _speed(c, req, f), _voltage(c, req, f), *_fit(c, f, fit)]


def verdict(checks: list[SpecCheck]) -> Verdict:
    """05 section 5: any fail -> rejected; else any review -> review; else pass (Pass*)."""
    verdicts = {ch.verdict for ch in checks}
    if "fail" in verdicts:
        return "rejected"
    return "review" if "review" in verdicts else "pass"


def fit_badge(
    overall: Verdict, frame: str | None, baseline_frame: str, fit: dict[str, Any] | None
) -> FitBadge | None:
    """drop_in: Pass*, same frame, no hub adapter. close: Pass* otherwise. Rejected: none."""
    if overall == "rejected":
        return None
    if overall == "review":
        return "needs_review"
    same = frame == baseline_frame and fit is not None and not fit["needs_hub_adapter"]
    return "drop_in" if same else "close"
