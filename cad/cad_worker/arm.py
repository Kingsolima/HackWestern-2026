"""AR4 robot arm with the J2 (shoulder) drive in context. Owner 1. BUILD-PLAN-v4 §7.

Two layers:
- The arm itself is Annin's real AR4 (MK3) link meshes from ycheng517/ar4_ros_driver (MIT),
  posed by ar4_meshes.py. They are display only (GLB, not STEP) and never change.
- The J2 drive is generated here with CadQuery and changes with the motor: gearbox, mount
  plate, motor, shaft and, when needed, a bore sleeve. Annin's own J2 motor is cut out of the
  link_1 mesh so this drive replaces it.

Joint layout from the AR4 URDF: J2 sits 64.2 mm in front of the J1 axis and 169.8 mm up, the
upper arm is 305 mm (J2 to J3) and the forearm about 223 mm (J3 to the wrist).

World frame: Z up, J1 axis is the Z axis, the arm reaches towards +X. The J2 axis runs along Y.
The J2 drive hangs off the turret's -Y side plate (y = -57.1 on the real mesh), outward along -Y:

    turret face | gearbox (output into the turret) | mount plate | motor body ->  -Y

The mount plate is the part the redesign regenerates: motor face on one side (bolt square,
pilot hole), the gearbox's fixed NEMA 23 input on the other.
"""

import math
from dataclasses import asdict, dataclass

import cadquery as cq

from cad_worker.ar4_meshes import TURRET_FACE_Y, posed_links
from cad_worker.export import Mesh
from cad_worker.nema import BOLT_HOLE_MM, NEMA, SHAFT_MM
from cad_worker.robot import BRACKET_COLOR, HIGHLIGHT_COLOR, _box, _cylinder, motor

# J2 axis position from the AR4 URDF (mm).
J2_X = 64.2
J2_Z = 169.8


# Baseline gearbox: 50:1 planetary with a NEMA 23 input (its input side stays fixed).
GEARBOX_FLANGE = 60.0
GEARBOX_FLANGE_T = 10.0
GEARBOX_LEN = 75.0
GEARBOX_INPUT_BOLT_CIRCLE = 66.68  # NEMA 23 bolt circle (47.14 * sqrt 2)

PLATE_T = 8.0
PLATE_MARGIN = 5.0
SLEEVE_LEN = 15.0

GEARBOX_COLOR = cq.Color(0.35, 0.35, 0.35)
MOTOR_COLOR = cq.Color(0.12, 0.12, 0.13)  # black stepper can, like the real AR4's


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
    """The generated J2 drive, in world coordinates. The arm around it is `arm_meshes()`."""
    m = measure_arm(p)
    shaft_d = m["shaft_diameter_mm"]
    _, pilot, _, _ = _dims(p)

    gb_out = TURRET_FACE_Y  # gearbox output face on the turret's side plate
    gb_in = gb_out - GEARBOX_LEN  # gearbox input face
    plate_out = gb_in - PLATE_T  # motor face

    assy = cq.Assembly(name="ar4")
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
        color=MOTOR_COLOR,
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
    return assy


def arm_meshes() -> list[Mesh]:
    """Annin's AR4 links around the drive, for the GLB only."""
    return posed_links()
