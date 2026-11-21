"""NEMA frame lookup table (ARCHITECTURE §5). Bolt patterns come from here, never from an LLM.

Typical values. Owner 3: check each against a real vendor drawing before building.
The CAD worker keeps a copy in cad/cad_worker/nema.py; keep them in sync.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NemaFrame:
    frame: str
    bolt_spacing_mm: float  # square bolt-hole spacing
    pilot_diameter_mm: float
    common_shaft_mm: tuple[float, ...]
    face_mm: float  # approximate square face width


NEMA: dict[str, NemaFrame] = {
    "17": NemaFrame("17", 31.0, 22.0, (5.0,), 42.3),
    "23": NemaFrame("23", 47.14, 38.1, (6.35, 8.0), 57.2),
    "34": NemaFrame("34", 69.6, 73.0, (9.5, 12.7, 14.0), 86.0),
}


def lookup(frame: str | None) -> NemaFrame | None:
    if frame is None:
        return None
    return NEMA.get(frame.strip().upper().removeprefix("NEMA").strip())
