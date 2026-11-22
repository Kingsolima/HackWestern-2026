"""Arm-joint requirement (docs/BUILD-PLAN-v4.md section 6). Worst static case: the arm straight
out horizontally with the payload at full reach. Links are point masses at their centres of
mass, so their own rotational inertia is left out; the safety factor covers it. The result is
the motor-side Requirement the v3 checks already use."""

import math

from app.engineering.spec_checks import G, Requirement
from app.schemas import ArmParams


def joint_torques_nm(a: ArmParams) -> tuple[float, float]:
    """(hold, peak) torque at the joint itself, before gearbox and safety factor."""
    hold = G * (a.payload_kg * a.reach_m + sum(link.mass_kg * link.com_m for link in a.links))
    inertia = a.payload_kg * a.reach_m**2 + sum(link.mass_kg * link.com_m**2 for link in a.links)
    alpha = math.radians(a.omega_max_dps) / a.t_accel_s
    return hold, hold + inertia * alpha


def arm_requirement(a: ArmParams) -> Requirement:
    hold, peak = joint_torques_nm(a)
    motor_side = a.safety_factor / (a.gear_ratio * a.efficiency)
    return Requirement(
        t_cont_nm=hold * motor_side,
        t_peak_nm=peak * motor_side,
        w_rpm=a.omega_max_dps / 360 * 60 * a.gear_ratio,
        v_bus=a.bus_voltage_v,
    )
