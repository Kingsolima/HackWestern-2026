"""Measure an uploaded STEP file for onboarding (backend/app/intake/from_cad.py reads the result).

Per part: its name, the sides of its bounding box and its volume. Names come from the STEP's
assembly structure; a file without one gives unnamed solids. Nothing is inferred here: which part
is a wheel or a motor is decided by the backend's rules.
"""

from pathlib import Path

import cadquery as cq


def _sides(shape: cq.Shape) -> list[float]:
    box = shape.BoundingBox()
    return [round(box.xlen, 3), round(box.ylen, 3), round(box.zlen, 3)]


def _part(name: str, shape: cq.Shape) -> dict:
    return {"name": name, "bbox_mm": _sides(shape), "volume_mm3": round(shape.Volume(), 1)}


def measure_step(path: Path) -> dict:
    """Raises ValueError when the file is not a STEP model with at least one solid."""
    try:
        whole = cq.importers.importStep(str(path))
    except Exception as exc:  # OCCT raises its own types for an unreadable file
        raise ValueError(f"not a readable STEP file: {exc}") from exc
    solids = whole.solids().vals()
    if not solids:
        raise ValueError("the STEP file has no solids")

    try:
        assy = cq.Assembly.importStep(str(path))
        # Names are paths from the root ("robot/wheel_left"): keep the part's own name.
        parts = [_part(name.rsplit("/", 1)[-1], shape) for shape, name, _, _ in assy]
    except Exception:
        parts = []
    if not parts:
        parts = [_part("", solid) for solid in solids]

    compound = cq.Compound.makeCompound(solids)
    return {
        "parts": parts,
        "bbox_mm": _sides(compound),
        "volume_mm3": round(sum(s.Volume() for s in solids), 1),
    }
