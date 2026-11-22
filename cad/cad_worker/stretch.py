"""Stretch-style mobile manipulator with the arm shoulder drive in context. BUILD-PLAN-v4 §7.

A block-level model of our own: a wheeled base, a mast and one arm link. None of the sizes are
Boston Dynamics' (they publish no drawings); they only put the shoulder drive in a believable
place. The shoulder drive is laid out like the AR4's J2 drive (arm.py):

    mast face | gearbox (output into the mast) | mount plate | motor body ->  -Y

World frame: Z up, the arm reaches towards +X, the shoulder axis runs along Y. The mount plate
is the part the redesign regenerates.
"""

import math
from dataclasses import asdict, dataclass

import cadquery as cq

from cad_worker.nema import BOLT_HOLE_MM, NEMA
from cad_worker.robot import BRACKET_COLOR, HIGHLIGHT_COLOR, _box, _cylinder, motor

BASE_L, BASE_W, BASE_H = 1100.0, 700.0, 250.0
BASE_Z0 = 60.0  # underside of the base above the floor
WHEEL_R, WHEEL_W = 110.0, 60.0

MAST_X = -300.0
MAST_SIDE = 200.0  # square mast; side faces at y = ±100
MAST_H = 1000.0
SHOULDER_Z = BASE_Z0 + BASE_H + MAST_H - 120.0
ARM_LEN = 900.0

# Strain-wave gearbox with a NEMA 34 input (its input side stays fixed).
GEARBOX_FLANGE = 110.0
GEARBOX_LEN = 60.0
GEARBOX_INPUT_BOLT_CIRCLE = 98.43  # NEMA 34 bolt circle (69.6 * sqrt 2)

PLATE_T = 10.0
PLATE_MARGIN = 5.0
SLEEVE_LEN = 20.0

BODY_COLOR = cq.Color(0.2, 0.2, 0.22)
ARM_COLOR = cq.Color(0.85, 0.85, 0.88)
GEARBOX_COLOR = cq.Color(0.35, 0.35, 0.35)


@dataclass
class StretchParams:
    frame: str = "34"
    body_len: float = 120.0
    # None = the gearbox bore, so the baseline motor fits without a sleeve.
    shaft_d: float | None = None
    pilot_d: float | None = None  # None = NEMA table
    bolt_spacing: float | None = None  # None = NEMA table
    # Assumed, not measured (no public drawing): 14 mm is a common NEMA 34 shaft.
    gearbox_bore: float = 14.0
    # Room beside the mast before the drive sticks out past the base: (BASE_W - MAST_SIDE) / 2.
    shoulder_space: float = 250.0
    highlight: bool = False


def _dims(p: StretchParams) -> tuple[float, float, float, float]:
    spacing, pilot, flange = NEMA[p.frame]
    return (
        p.bolt_spacing if p.bolt_spacing is not None else spacing,
        p.pilot_d if p.pilot_d is not None else pilot,
        flange,
        p.shaft_d if p.shaft_d is not None else p.gearbox_bore,
    )


def measure_stretch(p: StretchParams) -> dict:
    """Geometry numbers for the checks. Pure arithmetic, no CAD."""
    spacing, pilot, flange, shaft_d = _dims(p)
    protrusion = GEARBOX_LEN + PLATE_T + p.body_len
    shaft_fits = shaft_d <= p.gearbox_bore + 0.01
    return {
        "robot": "stretch",
        "illustrative": True,
        "params": asdict(p),
        "flange_mm": flange,
        "shaft_diameter_mm": shaft_d,
        "gearbox_bore_mm": p.gearbox_bore,
        "needs_bore_sleeve": shaft_fits and not math.isclose(shaft_d, p.gearbox_bore, abs_tol=0.01),
        "shoulder_protrusion_mm": round(protrusion, 2),
        "shoulder_space_mm": p.shoulder_space,
        "mount": {
            "thickness_mm": PLATE_T,
            "size_mm": max(flange, GEARBOX_FLANGE) + 2 * PLATE_MARGIN,
            "bolt_spacing_mm": spacing,
            "pilot_hole_mm": pilot + 1.0,
            "bolt_hole_mm": BOLT_HOLE_MM[p.frame],
            "gearbox_bolt_circle_mm": GEARBOX_INPUT_BOLT_CIRCLE,
        },
        "fit_checks": [
            {
                "name": "shoulder_envelope",
                "value": round(protrusion, 2),
                "limit": p.shoulder_space,
                "unit": "mm",
                "ok": protrusion <= p.shoulder_space,
            },
            {
                "name": "shaft_to_gearbox_bore",
                "value": shaft_d,
                "limit": p.gearbox_bore,
                "unit": "mm",
                "ok": shaft_fits,
            },
        ],
    }


def _along_y(r: float, y0: float, y1: float, x: float = MAST_X, z: float = SHOULDER_Z):
    """Cylinder on an axis parallel to Y, from y0 to y1."""
    lo, hi = min(y0, y1), max(y0, y1)
    return _cylinder(r, hi - lo, (x, lo, z))


def mount_plate(p: StretchParams) -> cq.Workplane:
    """Adapter plate in a local frame: shoulder axis on the origin, plate from y=0 to PLATE_T."""
    spacing, pilot, flange, _ = _dims(p)
    size = max(flange, GEARBOX_FLANGE) + 2 * PLATE_MARGIN
    plate = _box(size, PLATE_T, size, (0, PLATE_T / 2, 0))
    plate = plate.cut(_cylinder((pilot + 1.0) / 2, PLATE_T + 2, (0, -1, 0)))
    r = BOLT_HOLE_MM[p.frame] / 2
    for dx in (-spacing / 2, spacing / 2):  # motor bolt square
        for dz in (-spacing / 2, spacing / 2):
            plate = plate.cut(_cylinder(r, PLATE_T + 2, (dx, -1, dz)))
    gb = GEARBOX_INPUT_BOLT_CIRCLE / 2  # gearbox bolts on the axes, clear of the corners
    for dx, dz in ((gb, 0), (-gb, 0), (0, gb), (0, -gb)):
        plate = plate.cut(_cylinder(2.75, PLATE_T + 2, (dx, -1, dz)))
    return plate


def stretch(p: StretchParams) -> cq.Assembly:
    m = measure_stretch(p)
    shaft_d = m["shaft_diameter_mm"]
    _, pilot, _, _ = _dims(p)
    half = MAST_SIDE / 2

    gb_out = -half  # gearbox output face on the mast
    gb_in = gb_out - GEARBOX_LEN  # gearbox input face
    plate_out = gb_in - PLATE_T  # motor face

    assy = cq.Assembly(name="stretch")
    assy.add(
        _box(BASE_L, BASE_W, BASE_H, (0, 0, BASE_Z0 + BASE_H / 2)), name="base", color=BODY_COLOR
    )
    for sx, x in (("front", BASE_L / 2 - 180), ("rear", -BASE_L / 2 + 180)):
        for sy, y in (("left", BASE_W / 2), ("right", -BASE_W / 2 - WHEEL_W)):
            assy.add(
                _cylinder(WHEEL_R, WHEEL_W, (x, y, WHEEL_R)),
                name=f"wheel_{sx}_{sy}",
                color=cq.Color("black"),
            )
    mast_z0 = BASE_Z0 + BASE_H
    assy.add(
        _box(MAST_SIDE, MAST_SIDE, MAST_H, (MAST_X, 0, mast_z0 + MAST_H / 2)),
        name="mast",
        color=BODY_COLOR,
    )

    # Shoulder drive
    assy.add(
        _along_y(GEARBOX_FLANGE / 2, gb_out, gb_in), name="shoulder_gearbox", color=GEARBOX_COLOR
    )
    assy.add(
        mount_plate(p).translate((MAST_X, plate_out, SHOULDER_Z)),
        name="mount_plate",
        color=HIGHLIGHT_COLOR if p.highlight else BRACKET_COLOR,
    )
    assy.add(
        motor(p.frame, p.body_len, pilot).translate((MAST_X, plate_out, SHOULDER_Z)),
        name="shoulder_motor",
        color=cq.Color("blue"),
    )
    assy.add(
        _along_y(shaft_d / 2, plate_out, gb_in + SLEEVE_LEN),
        name="shoulder_motor_shaft",
        color=cq.Color(0.75, 0.75, 0.75),
    )
    if m["needs_bore_sleeve"]:
        assy.add(
            _along_y(p.gearbox_bore / 2 + 4, gb_in - 4, gb_in + SLEEVE_LEN),
            name="bore_sleeve",
            color=cq.Color("red"),
        )

    # Arm on the other side of the mast, reaching forward, with a suction gripper pad.
    y_arm = half + 50
    assy.add(_along_y(70, half, half + 100), name="shoulder_hub", color=ARM_COLOR)
    assy.add(
        _box(ARM_LEN, 80, 110, (MAST_X + ARM_LEN / 2, y_arm, SHOULDER_Z)),
        name="arm",
        color=ARM_COLOR,
    )
    assy.add(
        _box(40, 320, 320, (MAST_X + ARM_LEN + 20, y_arm, SHOULDER_Z)),
        name="gripper",
        color=BODY_COLOR,
    )
    return assy
