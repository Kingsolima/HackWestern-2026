"""Parametric robot (ARCHITECTURE §5). Owner 1.

Clean and labelled beats realistic. Only the motor bracket changes between designs.

World frame: X forward, Y left, Z up, ground at z=0. The robot is a differential drive:
two direct-drive wheels on a rear axle plus a front caster. Each motor's shaft points
outward along Y, straight into its wheel's hub, so the motor axis height equals the
wheel radius.

Parts are built in a per-side local frame: motor axis along +Y (towards the wheel),
x=0 and z=0 on the motor axis, y=0 at the motor's mounting face. The right side is
the left side rotated 180° about Z.
"""

from dataclasses import dataclass

import cadquery as cq

from cad_worker.nema import BOLT_HOLE_MM, NEMA, SHAFT_MM

BRACKET_T = 5.0  # bracket plate thickness
BRACKET_MARGIN = 5.0  # bracket material around the motor face
EDGE_INSET = 5.0  # bracket outer face inset from the base plate's edge


@dataclass
class RobotParams:
    frame: str = "23"
    body_len: float = 56.0
    clearance: float = 5.0
    plate_l: float = 300.0
    plate_w: float = 220.0
    plate_t: float = 6.0
    ground_clearance: float = 10.0  # floor to the underside of the plate
    wheel_r: float = 70.0  # big enough that a NEMA 34 still clears the plate
    wheel_w: float = 25.0
    wheel_gap: float = 10.0  # plate edge to the wheel's inner face
    axle_from_rear: float = 70.0


def _cylinder(r: float, length: float, start, direction=(0, 1, 0)) -> cq.Workplane:
    solid = cq.Solid.makeCylinder(r, length, cq.Vector(*start), cq.Vector(*direction))
    return cq.Workplane("XY").add(solid)


def _box(dx: float, dy: float, dz: float, center) -> cq.Workplane:
    return cq.Workplane("XY").box(dx, dy, dz).translate(center)


def motor(frame: str, body_len: float) -> cq.Workplane:
    """NEMA motor body in the local frame: face at y=0, body towards -Y, pilot boss to +Y."""
    _, pilot, face = NEMA[frame]
    body = _box(face, body_len, face, (0, -body_len / 2, 0))
    boss = _cylinder(pilot / 2, 2.0, (0, 0, 0))
    return body.union(boss)


def shaft(frame: str, length: float) -> cq.Workplane:
    return _cylinder(SHAFT_MM[frame] / 2, length, (0, 0, 0))


def bracket(
    frame: str, body_len: float, clearance: float, axis_height: float | None = None
) -> cq.Workplane:
    """L-bracket in the local frame.

    The upright (y in [0, T]) carries the NEMA bolt square and pilot hole on the motor
    axis, `axis_height` above the plate's top surface. The foot lies flat on the plate
    and runs inboard under the motor body; its depth follows `body_len`.
    Bolt spacing and pilot diameter come from the NEMA table, never from a datasheet.
    """
    spacing, pilot, face = NEMA[frame]
    if axis_height is None:
        axis_height = face / 2 + BRACKET_T
    width = face + 2 * BRACKET_MARGIN
    height = axis_height + face / 2 + BRACKET_MARGIN
    upright = _box(width, BRACKET_T, height, (0, BRACKET_T / 2, -axis_height + height / 2))

    foot_len = body_len + clearance + BRACKET_T
    foot = _box(
        width,
        foot_len,
        BRACKET_T,
        (0, BRACKET_T - foot_len / 2, -axis_height + BRACKET_T / 2),
    )

    body = upright.union(foot)
    body = body.cut(_cylinder((pilot + 1.0) / 2, BRACKET_T + 2, (0, -1, 0)))
    r = BOLT_HOLE_MM[frame] / 2
    for dx in (-spacing / 2, spacing / 2):
        for dz in (-spacing / 2, spacing / 2):
            body = body.cut(_cylinder(r, BRACKET_T + 2, (dx, -1, dz)))
    return body


def robot(p: RobotParams) -> cq.Assembly:
    face = NEMA[p.frame][2]
    plate_top = p.ground_clearance + p.plate_t
    axle_z = p.wheel_r  # wheels touch the ground
    axis_height = axle_z - plate_top
    if axis_height - BRACKET_T < face / 2:
        raise ValueError(f"NEMA {p.frame} does not clear the plate with wheel_r={p.wheel_r}")

    axle_x = -p.plate_l / 2 + p.axle_from_rear
    motor_face_y = p.plate_w / 2 - EDGE_INSET - BRACKET_T  # inner face of the bracket
    wheel_center_y = p.plate_w / 2 + p.wheel_gap + p.wheel_w / 2

    assy = cq.Assembly(name="robot")
    assy.add(
        _box(p.plate_l, p.plate_w, p.plate_t, (0, 0, p.ground_clearance + p.plate_t / 2)),
        name="base_plate",
        color=cq.Color("gray"),
    )
    assy.add(
        _box(120, 80, 50, (40, 0, plate_top + 25)),
        name="electronics_box",
        color=cq.Color("black"),
    )
    caster_r = p.ground_clearance
    assy.add(
        cq.Workplane("XY").sphere(caster_r).translate((p.plate_l / 2 - 30, 0, caster_r)),
        name="caster",
        color=cq.Color(0.75, 0.75, 0.75),
    )

    for side, angle in (("left", 0), ("right", 180)):
        loc = cq.Location(cq.Vector(axle_x, 0, axle_z)) * cq.Location(
            cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), angle
        )
        assy.add(
            bracket(p.frame, p.body_len, p.clearance, axis_height).translate((0, motor_face_y, 0)),
            name=f"bracket_{side}",
            loc=loc,
            color=cq.Color("orange"),
        )
        assy.add(
            motor(p.frame, p.body_len).translate((0, motor_face_y, 0)),
            name=f"motor_{side}",
            loc=loc,
            color=cq.Color("blue"),
        )
        assy.add(
            shaft(p.frame, wheel_center_y - motor_face_y).translate((0, motor_face_y, 0)),
            name=f"shaft_{side}",
            loc=loc,
            color=cq.Color(0.75, 0.75, 0.75),
        )
        assy.add(
            _cylinder(p.wheel_r, p.wheel_w, (0, wheel_center_y - p.wheel_w / 2, 0)),
            name=f"wheel_{side}",
            loc=loc,
            color=cq.Color(0.1, 0.1, 0.1),
        )
    return assy
