"""NEMA lookup table. Copy of backend/app/engineering/nema.py; keep them in sync."""

NEMA = {
    # frame: (bolt_spacing_mm, pilot_diameter_mm, face_mm)
    "17": (31.0, 22.0, 42.3),
    "23": (47.14, 38.1, 57.2),
    "34": (69.6, 73.0, 86.0),
}
# Bolt holes per docs/design/05-checks-spec.md §4 (17: M3 clearance; 23/34: approx. through
# holes). Verify each against a vendor drawing before the demo.
BOLT_HOLE_MM = {"17": 3.4, "23": 5.1, "34": 5.5}
# Common shaft diameter per frame (first value from the ARCHITECTURE §5 table).
SHAFT_MM = {"17": 5.0, "23": 6.35, "34": 9.5}
