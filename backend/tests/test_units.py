import math

import pytest

from app.engineering.units import canonical_unit, to_si


@pytest.mark.parametrize(
    ("unit", "value", "si"),
    [
        ("oz-in", 100, (0.70615518, "N·m")),
        ("Oz.In", 100, (0.70615518, "N·m")),
        ("lbf-in", 1, (0.112984829, "N·m")),
        ("lb-ft", 1, (1.35581795, "N·m")),
        ("kg-cm", 1, (0.0980665, "N·m")),
        ("mNm", 500, (0.5, "N·m")),
        ("N m", 2, (2.0, "N·m")),
        ("RPM", 4000, (4000.0, "rpm")),
        ("in", 3.34, (84.836, "mm")),
        ("VDC", 24, (24.0, "V")),
        ("$", 265, (265.0, "USD")),
    ],
)
def test_to_si(unit, value, si):
    got = to_si(value, unit)
    assert got is not None and got[1] == si[1] and math.isclose(got[0], si[0], rel_tol=1e-9)


@pytest.mark.parametrize("unit", [None, "furlongs", "CAD", "oz"])
def test_unknown_units_stay_unconverted(unit):
    assert to_si(1, unit) is None
    assert canonical_unit(unit) is None
