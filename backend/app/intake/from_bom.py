"""Spec numbers that can be read straight off the BOM (wheeled robot). Code only: each rule is a
pattern on one row, and the row is the evidence."""

import re

from app.intake.schema import Found
from app.schemas import BomRow

_NUM = r"(\d+(?:\.\d+)?)"
_VOLTS = re.compile(_NUM + r"\s*V(?:DC)?\b", re.I)
_RATIO = re.compile(_NUM + r"\s*:\s*1\b")
_MM = re.compile(_NUM + r"\s*mm\b", re.I)
_DIAMETER = re.compile(r"\b(dia|diameter|od)\b|⌀|ø", re.I)
_RADIUS = re.compile(r"\bradius\b", re.I)


def _row(r: BomRow) -> str:
    return f"{r.qty} x {r.part}"


def _is(r: BomRow, *words: str) -> bool:
    text = f"{r.category} {r.part}".lower()
    return any(re.search(rf"\b{w}", text) for w in words)


def specs_from_bom(bom: list[BomRow]) -> list[Found]:
    found: list[Found] = []

    def add(field: str, value: float, row: BomRow) -> None:
        if all(f.field != field for f in found):
            found.append(Found(field=field, value=value, source="bom", evidence=_row(row)))

    motors = [r for r in bom if r.category.strip().lower() == "motor"]
    if motors:
        found.append(
            Found(
                field="n_drive_motors",
                value=sum(r.qty for r in motors),
                source="bom",
                evidence=", ".join(_row(r) for r in motors),
            )
        )
    for r in bom:
        if _is(r, "battery", "power supply") and (m := _VOLTS.search(r.part)):
            add("bus_voltage_v", float(m[1]), r)
        if _is(r, "gear") and (m := _RATIO.search(r.part)):
            add("gear_ratio", float(m[1]), r)
        if _is(r, "wheel") and not _is(r, "encoder") and (m := _MM.search(r.part)):
            if _RADIUS.search(r.part):
                add("wheel_radius_mm", float(m[1]), r)
            elif _DIAMETER.search(r.part):
                add("wheel_radius_mm", float(m[1]) / 2, r)
    return found
