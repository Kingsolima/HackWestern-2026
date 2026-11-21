"""Parametric robot (HANDOFF-v3 §2.13, docs/design/05-checks-spec.md §4). Owner 1.

v3 demo robot: ~5 kg, direct drive (G = 1), 60 mm wheel radius, NEMA servo baseline.

World frame: X forward, Y left, Z up, ground at z=0. Differential drive: two direct-drive
wheels on a rear axle plus a front caster. Each motor's shaft points outward along Y into its
wheel's hub, so the motor axis height equals the wheel radius.

The flange hangs below the axle, so the deck height follows the motor (05 §4 fit_ground):
    ground_clearance = r - flange/2 - clearance - bracket_t - deck_t
A NEMA 34 on 60 mm wheels leaves almost nothing. The model still builds (so the viewer can
show why) and `measure()` reports it; the engineering checks decide the verdict.

Parts are built in a per-side local frame: motor axis along +Y (towards the wheel), x=0 and
z=0 on the motor axis, y=0 at the motor's mounting face. The right side is the left side
rotated 180° about Z.
"""

import math
from dataclasses import asdict, dataclass

import cadquery as cq

from cad_worker.nema import BOLT_HOLE_MM, NEMA, SHAFT_MM

BRACKET_T = 5.0  # bracket plate thickness (05 §4 "plate_t")
BRACKET_MARGIN = 5.0  # bracket material around the motor face
EDGE_INSET = 5.0  # bracket outer face inset from the deck edge
CENTER_GAP = 5.0  # space kept free on the robot's centre line between the two motors
ADAPTER_LEN = 12.0


@dataclass
class RobotParams:
    frame: str = "23"
    body_len: float = 56.0
    shaft_d: float | None = None  # None = common shaft for the frame (NEMA table)
    clearance: float = 5.0  # gap between motor flange and bracket foot
    deck_l: float = 300.0
    deck_w: float = 220.0
    deck_t: float = 6.0
    wheel_r: float = 60.0
    wheel_w: float = 25.0
    wheel_gap: float = 10.0  # deck edge to the wheel's inner face
    wheel_bore: float = 6.35  # baseline NEMA 23 shaft
    axle_from_rear: float = 70.0
    min_ground_clearance: float = 10.0


def _cylinder(r: float, length: float, start, direction=(0, 1, 0)) -> cq.Workplane:
    solid = cq.Solid.makeCylinder(r, length, cq.Vector(*start), cq.Vector(*direction))
    return cq.Workplane("XY").add(solid)


def _box(dx: float, dy: float, dz: float, center) -> cq.Workplane:
    return cq.Workplane("XY").box(dx, dy, dz).translate(center)


def _shaft_d(p: RobotParams) -> float:
    return p.shaft_d if p.shaft_d is not None else SHAFT_MM[p.frame]


def measure(p: RobotParams) -> dict:
    """Geometry numbers the engineering checks need (05 §4). Pure arithmetic, no CAD."""
    spacing, pilot, flange = NEMA[p.frame]
    deck_top = p.wheel_r - flange / 2 - p.clearance - BRACKET_T
    ground = deck_top - p.deck_t
    inboard_room = p.deck_w / 2 - EDGE_INSET - CENTER_GAP
    envelope_used = p.body_len + BRACKET_T + p.clearance
    shaft_d = _shaft_d(p)
    axis_above_deck = p.wheel_r - deck_top
    return {
        "params": asdict(p),
        "flange_mm": flange,
        "axle_height_mm": p.wheel_r,
        "deck_top_mm": round(deck_top, 2),
        "ground_clearance_mm": round(ground, 2),
        "fit_ground": ground >= p.min_ground_clearance,
        "inboard_room_mm": inboard_room,
        "envelope_used_mm": round(envelope_used, 2),
        "fit_envelope": envelope_used <= inboard_room,
        "shaft_diameter_mm": shaft_d,
        "wheel_bore_mm": p.wheel_bore,
        "needs_hub_adapter": not math.isclose(shaft_d, p.wheel_bore, abs_tol=0.01),
        "bracket": {
            "width_mm": flange + 2 * BRACKET_MARGIN,
            "height_mm": round(axis_above_deck + flange / 2 + BRACKET_MARGIN, 2),
            "foot_len_mm": round(p.body_len + p.clearance + BRACKET_T, 2),
            "bolt_spacing_mm": spacing,
            "pilot_hole_mm": pilot + 1.0,
            "bolt_hole_mm": BOLT_HOLE_MM[p.frame],
        },
    }


def motor(frame: str, body_len: float) -> cq.Workplane:
    """NEMA motor body in the local frame: face at y=0, body towards -Y, pilot boss to +Y."""
    _, pilot, face = NEMA[frame]
    body = _box(face, body_len, face, (0, -body_len / 2, 0))
    boss = _cylinder(pilot / 2, 2.0, (0, 0, 0))
    return body.union(boss)


def shaft(diameter: float, length: float) -> cq.Workplane:
    return _cylinder(diameter / 2, length, (0, 0, 0))


def bracket(
    frame: str, body_len: float, clearance: float, axis_height: float | None = None
) -> cq.Workplane:
    """L-bracket in the local frame.

    The upright (y in [0, T]) carries the NEMA bolt square and pilot hole on the motor
    axis, `axis_height` above the deck's top surface. The foot lies flat on the deck and
    runs inboard under the motor body; its depth follows `body_len`.
    Bolt spacing and pilot diameter come from the NEMA table, never from a datasheet.
    """
    spacing, pilot, face = NEMA[frame]
    if axis_height is None:
        axis_height = face / 2 + clearance + BRACKET_T
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
    m = measure(p)
    deck_top = m["deck_top_mm"]
    ground = m["ground_clearance_mm"]
    axle_z = p.wheel_r
    shaft_d = m["shaft_diameter_mm"]

    axle_x = -p.deck_l / 2 + p.axle_from_rear
    motor_face_y = p.deck_w / 2 - EDGE_INSET - BRACKET_T  # inner face of the bracket
    wheel_inner_y = p.deck_w / 2 + p.wheel_gap
    wheel_center_y = wheel_inner_y + p.wheel_w / 2

    assy = cq.Assembly(name="robot")
    assy.add(
        _box(p.deck_l, p.deck_w, p.deck_t, (0, 0, deck_top - p.deck_t / 2)),
        name="base_plate",
        color=cq.Color("gray"),
    )
    assy.add(
        _box(120, 80, 50, (40, 0, deck_top + 25)),
        name="electronics_box",
        color=cq.Color("black"),
    )
    if ground > 0:  # no room for a caster when the deck is on the floor; measure() flags it
        caster_r = ground / 2
        assy.add(
            cq.Workplane("XY").sphere(caster_r).translate((p.deck_l / 2 - 30, 0, caster_r)),
            name="caster",
            color=cq.Color(0.75, 0.75, 0.75),
        )

    for side, angle in (("left", 0), ("right", 180)):
        loc = cq.Location(cq.Vector(axle_x, 0, axle_z)) * cq.Location(
            cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), angle
        )
        assy.add(
            bracket(p.frame, p.body_len, p.clearance, axle_z - deck_top).translate(
                (0, motor_face_y, 0)
            ),
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
            shaft(shaft_d, wheel_center_y - motor_face_y).translate((0, motor_face_y, 0)),
            name=f"shaft_{side}",
            loc=loc,
            color=cq.Color(0.75, 0.75, 0.75),
        )
        assy.add(
            _cylinder(p.wheel_r, p.wheel_w, (0, wheel_inner_y, 0)),
            name=f"wheel_{side}",
            loc=loc,
            color=cq.Color(0.1, 0.1, 0.1),
        )
        if m["needs_hub_adapter"]:
            od = max(shaft_d, p.wheel_bore) + 10
            assy.add(
                _cylinder(od / 2, ADAPTER_LEN, (0, wheel_inner_y - ADAPTER_LEN, 0)),
                name=f"hub_adapter_{side}",
                loc=loc,
                color=cq.Color("red"),
            )
    return assy
