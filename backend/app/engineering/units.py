"""Unit table (docs/design/05 section 1). The LLM never converts; an unknown unit stays None,
so any check that needs the value becomes Review."""

import re

_FACTORS: dict[str, tuple[str, float]] = {
    "n-m": ("N·m", 1.0),
    "mn-m": ("N·m", 0.001),
    "oz-in": ("N·m", 0.0070615518),
    "lb-in": ("N·m", 0.112984829),
    "lb-ft": ("N·m", 1.35581795),
    "kgf-cm": ("N·m", 0.0980665),
    "rpm": ("rpm", 1.0),
    "mm": ("mm", 1.0),
    "in": ("mm", 25.4),
    "v": ("V", 1.0),
    "a": ("A", 1.0),
    "usd": ("USD", 1.0),
}
_ALIASES = {
    "nm": "n-m",
    "n.m": "n-m",
    "n·m": "n-m",
    "mnm": "mn-m",
    "ozf-in": "oz-in",
    "oz.in": "oz-in",
    "ozin": "oz-in",
    "lbf-in": "lb-in",
    "lbf-ft": "lb-ft",
    "kg-cm": "kgf-cm",
    "vdc": "v",
    "vac": "v",
    "inch": "in",
    "inches": "in",
    '"': "in",
    "$": "usd",
    "us$": "usd",
}


def canonical_unit(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = re.sub(r"\s+", "", raw.strip().lower()).replace("–", "-")
    key = _ALIASES.get(key, key)
    return key if key in _FACTORS else None


def to_si(value: float, raw_unit: str | None) -> tuple[float, str] | None:
    """(value in SI, SI unit) or None when the unit is not in the table."""
    unit = canonical_unit(raw_unit)
    if unit is None:
        return None
    si_unit, factor = _FACTORS[unit]
    return value * factor, si_unit
