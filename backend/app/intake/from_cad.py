"""Spec numbers read from the uploaded CAD (wheeled robot), from what the CAD worker measured.

Part roles come from part names only (wheel_left, motor_right, ...). A STEP file carries no
material, so the mass is volume times an assumed density and is labelled an estimate.
"""

import re
from collections import Counter

from app.intake.schema import CadMeasure, Found

ALUMINIUM_KG_PER_MM3 = 2.70e-6
_WHEEL = re.compile(r"wheel", re.I)
_NOT_DRIVE_WHEEL = re.compile(r"caster|castor|encoder|hub|adapter", re.I)
_MOTOR = re.compile(r"motor", re.I)
_NOT_MOTOR = re.compile(r"bracket|mount|plate|driver|shaft|adapter", re.I)


def specs_from_cad(cad: CadMeasure) -> list[Found]:
    found: list[Found] = []

    wheels = [p for p in cad.parts if _WHEEL.search(p.name) and not _NOT_DRIVE_WHEEL.search(p.name)]
    if wheels:
        # A wheel's largest bounding-box side is its diameter. Rounded to 0.1 mm so tessellation
        # noise does not make a 60 mm wheel differ from the demo's.
        radii = Counter(round(max(p.bbox_mm) / 2, 1) for p in wheels)
        radius = radii.most_common(1)[0][0]
        names = ", ".join(p.name for p in wheels if round(max(p.bbox_mm) / 2, 1) == radius)
        found.append(
            Found(field="wheel_radius_mm", value=radius, source="cad", evidence=f"parts {names}")
        )

    motors = [p for p in cad.parts if _MOTOR.search(p.name) and not _NOT_MOTOR.search(p.name)]
    if motors:
        found.append(
            Found(
                field="n_drive_motors",
                value=len(motors),
                source="cad",
                evidence="parts " + ", ".join(p.name for p in motors),
            )
        )

    if cad.volume_mm3 > 0:
        litres = cad.volume_mm3 / 1e6
        found.append(
            Found(
                field="mass_kg",
                value=round(cad.volume_mm3 * ALUMINIUM_KG_PER_MM3, 2),
                source="cad",
                evidence=f"estimate: {litres:.2f} L of solid x 2.70 g/cm³ (aluminium assumed)",
            )
        )
    return found
