"""Parametric robot (ARCHITECTURE §5). Owner 1.

Clean and labelled beats realistic. Only the motor bracket changes between designs.
"""

from dataclasses import dataclass

import cadquery as cq

from cad_worker.nema import BOLT_HOLE_MM, NEMA

BRACKET_THICKNESS = 5.0


@dataclass
class RobotParams:
    frame: str = "23"
    body_len: float = 56.0
    clearance: float = 5.0
    plate_l: float = 300.0
    plate_w: float = 220.0
    plate_t: float = 6.0
    wheel_r: float = 50.0
    wheel_w: float = 25.0


def motor(frame: str, body_len: float) -> cq.Workplane:
    _, pilot, face = NEMA[frame]
    body = cq.Workplane("YZ").rect(face, face).extrude(body_len)
    boss = cq.Workplane("YZ").circle(pilot / 2).extrude(-2.0)
    return body.union(boss)


def bracket(frame: str, body_len: float, clearance: float) -> cq.Workplane:
    """L-bracket: vertical face with NEMA bolt pattern + pilot hole, horizontal foot."""
    spacing, pilot, face = NEMA[frame]
    width = face + 10
    height = face + 10
    foot = body_len + clearance
    plate = (
        cq.Workplane("YZ")
        .rect(width, height)
        .extrude(BRACKET_THICKNESS)
        .faces(">X")
        .workplane()
        .hole(pilot + 1.0)
        .faces(">X")
        .workplane()
        .rect(spacing, spacing, forConstruction=True)
        .vertices()
        .hole(BOLT_HOLE_MM[frame])
    )
    base = (
        cq.Workplane("XY")
        .box(foot, width, BRACKET_THICKNESS, centered=(False, True, False))
        .translate((-foot, 0, -height / 2))
    )
    return plate.union(base)


def robot(p: RobotParams) -> cq.Assembly:
    face = NEMA[p.frame][2]
    z_axis = p.plate_t + (face + 10) / 2  # motor axis height above the plate's bottom
    assy = cq.Assembly(name="robot")
    assy.add(
        cq.Workplane("XY").box(p.plate_l, p.plate_w, p.plate_t, centered=(True, True, False)),
        name="base_plate",
        color=cq.Color("gray"),
    )
    assy.add(
        cq.Workplane("XY").box(120, 80, 50, centered=(True, True, False)).translate((40, 0, p.plate_t)),
        name="electronics_box",
        color=cq.Color("black"),
    )
    for side, y in (("left", 1), ("right", -1)):
        y_mount = y * (p.plate_w / 2 - face / 2 - 10)
        loc = cq.Location(cq.Vector(-p.plate_l / 2 + 40, y_mount, z_axis))
        rot = cq.Location(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 90 * y)
        assy.add(
            bracket(p.frame, p.body_len, p.clearance),
            name=f"bracket_{side}",
            loc=loc * rot,
            color=cq.Color("orange"),
        )
        assy.add(
            motor(p.frame, p.body_len).translate((-p.body_len - BRACKET_THICKNESS, 0, 0)),
            name=f"motor_{side}",
            loc=loc * rot * cq.Location(cq.Vector(BRACKET_THICKNESS, 0, 0)),
            color=cq.Color("blue"),
        )
        wheel = cq.Workplane("XZ").circle(p.wheel_r).extrude(p.wheel_w / 2, both=True)
        assy.add(
            wheel,
            name=f"wheel_{side}",
            loc=cq.Location(cq.Vector(-p.plate_l / 2 + 40, y * (p.plate_w / 2 + p.wheel_w), p.wheel_r)),
            color=cq.Color("black"),
        )
    return assy
