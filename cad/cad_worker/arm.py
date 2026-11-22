"""AR4-style robot arm with the J2 (shoulder) drive in context. Owner 1. BUILD-PLAN-v4 §7.

The arm is our own simplified model, not Annin's meshes (those are licensed non-commercial).
Only the joint layout comes from the AR4 URDF in ycheng517/ar4_ros_driver (MIT): J2 sits
64.2 mm in front of the J1 axis and 169.8 mm up, the upper arm is 305 mm (J2 to J3) and the
forearm about 223 mm (J3 to the wrist).

World frame: Z up, J1 axis is the Z axis, the arm reaches towards +X. The J2 axis runs along Y.
The J2 drive hangs off the turret's -Y side, outward along -Y:

    turret face | gearbox (output into the turret) | mount plate | motor body ->  -Y

The mount plate is the part the redesign regenerates: motor face on one side (bolt square,
pilot hole), the gearbox's fixed NEMA 23 input on the other.
"""

import math
from dataclasses import asdict, dataclass

import cadquery as cq

from cad_worker.nema import BOLT_HOLE_MM, NEMA, SHAFT_MM
from cad_worker.robot import BRACKET_COLOR, HIGHLIGHT_COLOR, _box, _cylinder, motor

# Joint layout from the AR4 URDF (mm).
J2_X = 64.2
J2_Z = 169.8
UPPER_ARM = 305.0
FOREARM = 222.6

BASE_R, BASE_H = 80.0, 40.0
TURRET_HALF_W = 50.0  # turret side faces at y = ±50

# Baseline gearbox: 50:1 planetary with a NEMA 23 input (its input side stays fixed).
GEARBOX_FLANGE = 60.0
GEARBOX_FLANGE_T = 10.0
GEARBOX_LEN = 75.0
GEARBOX_INPUT_BOLT_CIRCLE = 66.68  # NEMA 23 bolt circle (47.14 * sqrt 2)

PLATE_T = 8.0
PLATE_MARGIN = 5.0
SLEEVE_LEN = 15.0

ARM_COLOR = cq.Color(0.85, 0.85, 0.88)
TURRET_COLOR = cq.Color(0.25, 0.25, 0.28)
GEARBOX_COLOR = cq.Color(0.35, 0.35, 0.35)


@dataclass
class ArmParams:
    frame: str = "23"
    body_len: float = 56.0
    shaft_d: float | None = None  # None = common shaft for the frame
    pilot_d: float | None = None  # None = NEMA table
    bolt_spacing: float | None = None  # None = NEMA table
    gearbox_bore: float = 6.35  # gearbox input bore (baseline NEMA 23 shaft)
    # Room beside the turret before the motor reaches the J1 sweep. Assumed, not measured:
    # check it on the club's arm and send the real number.
    j2_space: float = 190.0
    highlight: bool = False


def _dims(p: ArmParams) -> tuple[float, float, float, float]:
    spacing, pilot, flange = NEMA[p.frame]
    return (
        p.bolt_spacing if p.bolt_spacing is not None else spacing,
        p.pilot_d if p.pilot_d is not None else pilot,
        flange,
        p.shaft_d if p.shaft_d is not None else SHAFT_MM[p.frame],
    )


def measure_arm(p: ArmParams) -> dict:
    """Geometry numbers for the checks. Pure arithmetic, no CAD."""
    spacing, pilot, flange, shaft_d = _dims(p)
    protrusion = GEARBOX_LEN + PLATE_T + p.body_len
    shaft_fits = shaft_d <= p.gearbox_bore + 0.01
    return {
        "robot": "ar4",
        "params": asdict(p),
        "flange_mm": flange,
        "shaft_diameter_mm": shaft_d,
        "gearbox_bore_mm": p.gearbox_bore,
        "needs_bore_sleeve": shaft_fits and not math.isclose(shaft_d, p.gearbox_bore, abs_tol=0.01),
        "j2_protrusion_mm": round(protrusion, 2),
        "j2_space_mm": p.j2_space,
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
                "name": "j2_envelope",
                "value": round(protrusion, 2),
                "limit": p.j2_space,
                "unit": "mm",
                "ok": protrusion <= p.j2_space,
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


def _along_y(r: float, y0: float, y1: float, x: float = J2_X, z: float = J2_Z) -> cq.Workplane:
    """Cylinder on an axis parallel to Y, from y0 to y1."""
    lo, hi = min(y0, y1), max(y0, y1)
    return _cylinder(r, hi - lo, (x, lo, z))


def mount_plate(p: ArmParams) -> cq.Workplane:
    """Adapter plate in a local frame: J2 axis on the origin, plate from y=0 to y=PLATE_T."""
    spacing, pilot, _, _ = _dims(p)
    size = max(NEMA[p.frame][2], GEARBOX_FLANGE) + 2 * PLATE_MARGIN
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


def arm(p: ArmParams) -> cq.Assembly:
    m = measure_arm(p)
    shaft_d = m["shaft_diameter_mm"]
    _, pilot, _, _ = _dims(p)

    gb_out = -TURRET_HALF_W  # gearbox output face on the turret
    gb_in = gb_out - GEARBOX_LEN  # gearbox input face
    plate_out = gb_in - PLATE_T  # motor face

    assy = cq.Assembly(name="ar4")
    assy.add(_cylinder(BASE_R, BASE_H, (0, 0, 0), (0, 0, 1)), name="base", color=TURRET_COLOR)
    turret = _box(150, 2 * TURRET_HALF_W, J2_Z + 30 - BASE_H, (25, 0, (BASE_H + J2_Z + 30) / 2))
    assy.add(turret, name="turret", color=TURRET_COLOR)

    # J2 drive
    gearbox = _box(GEARBOX_FLANGE, GEARBOX_FLANGE_T, GEARBOX_FLANGE, (J2_X, gb_out - 5, J2_Z))
    gearbox = gearbox.union(_along_y(GEARBOX_FLANGE / 2 - 2, gb_out - GEARBOX_FLANGE_T, gb_in))
    assy.add(gearbox, name="j2_gearbox", color=GEARBOX_COLOR)
    assy.add(
        mount_plate(p).translate((J2_X, plate_out, J2_Z)),
        name="mount_plate",
        color=HIGHLIGHT_COLOR if p.highlight else BRACKET_COLOR,
    )
    assy.add(
        motor(p.frame, p.body_len, pilot).translate((J2_X, plate_out, J2_Z)),
        name="j2_motor",
        color=cq.Color("blue"),
    )
    assy.add(
        _along_y(shaft_d / 2, plate_out, gb_in + SLEEVE_LEN),
        name="j2_motor_shaft",
        color=cq.Color(0.75, 0.75, 0.75),
    )
    if m["needs_bore_sleeve"]:
        assy.add(
            _along_y(p.gearbox_bore / 2 + 3, gb_in - 3, gb_in + SLEEVE_LEN),
            name="bore_sleeve",
            color=cq.Color("red"),
        )
    assy.add(_along_y(10, gb_out, TURRET_HALF_W + 35), name="j2_output_shaft", color=GEARBOX_COLOR)

    # Arm in a reaching pose: upper arm straight up, forearm forward.
    y_arm = TURRET_HALF_W + 20
    j3_z = J2_Z + UPPER_ARM
    assy.add(_along_y(40, TURRET_HALF_W + 5, TURRET_HALF_W + 35), name="j2_hub", color=ARM_COLOR)
    assy.add(
        _box(60, 30, UPPER_ARM, (J2_X, y_arm, J2_Z + UPPER_ARM / 2)),
        name="upper_arm",
        color=ARM_COLOR,
    )
    assy.add(
        _along_y(32, TURRET_HALF_W + 5, TURRET_HALF_W + 35, z=j3_z), name="j3_hub", color=ARM_COLOR
    )
    assy.add(
        _box(FOREARM, 45, 45, (J2_X + FOREARM / 2, y_arm, j3_z)), name="forearm", color=ARM_COLOR
    )
    wrist_x = J2_X + FOREARM
    assy.add(_cylinder(20, 40, (wrist_x, y_arm, j3_z), (1, 0, 0)), name="wrist", color=TURRET_COLOR)
    assy.add(_box(20, 40, 30, (wrist_x + 50, y_arm, j3_z)), name="gripper", color=TURRET_COLOR)
    return assy
