"""Read the open answers with Gemini, then confirm every item in code.

The model only points at what the user wrote: a field, the value as written, its unit and the
exact quote. Code keeps an item only when the quote is in the user's text, the number is in the
quote, the unit converts and the result is in range. Nothing the model says becomes a number
without that (BUILD-PLAN-v4 section 1).
"""

import math
import re
from typing import Any

from app.intake.schema import Answers, CompanyFact, Found, Quantity, SpecField

# unit as written (lower case, no spaces) -> factor to the field's own unit
UNITS: dict[Quantity, dict[str, float]] = {
    "mass": {"kg": 1, "kgs": 1, "kilograms": 1, "g": 0.001, "lb": 0.45359237, "lbs": 0.45359237,
             "pounds": 0.45359237},
    "length": {"mm": 1, "cm": 10, "m": 1000, "in": 25.4, "inch": 25.4, "inches": 25.4, '"': 25.4},
    "speed": {"m/s": 1, "mps": 1, "km/h": 1 / 3.6, "kph": 1 / 3.6, "kmh": 1 / 3.6, "mph": 0.44704,
              "ft/s": 0.3048},
    "accel": {"m/s²": 1, "m/s^2": 1, "m/s2": 1, "m/s/s": 1},
    "angle": {"deg": 1, "degree": 1, "degrees": 1, "°": 1},
    "voltage": {"v": 1, "vdc": 1, "volt": 1, "volts": 1},
    "fraction": {"": 1, "%": 0.01, "percent": 0.01},
    "plain": {},  # any unit text is ignored: counts and ratios have none
    "money": {"usd": 1, "$": 1, "us$": 1, "dollars": 1, "": 1},
    "days": {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30},
}  # fmt: skip

# Numeric company facts, checked like specs.
COMPANY_NUMBERS: dict[str, tuple[str, Quantity]] = {
    "budget_usd": ("Parts budget per robot", "money"),
    "need_by_days": ("Needs parts in", "days"),
}
# Text company facts: label and what the extractor should put in `value`.
COMPANY_TEXT: dict[str, tuple[str, str]] = {
    "company_name": ("Name", "the company or team name"),
    "kind": ("Kind", "`company`, or `club` for a student club or research team"),
    "robot_name": ("Robot", "what the robot is called, or a short name for it"),
    "use_case": ("Use", "what the robot does, in a few of the user's words"),
    "sells_to_us_federal": ("Sells to US federal buyers", "`yes` or `no`"),
    "deploy_countries": ("Deployed in", "ISO 3166 two-letter codes, comma separated"),
    "final_assembly_country": ("Final assembly", "one ISO 3166 two-letter code"),
    "uptime_critical": ("Uptime critical", "`yes` if downtime is costly for users, else `no`"),
    "avoid": ("Wants to avoid", "suppliers, countries or materials to avoid, in their words"),
}
_CHOICES = {
    "kind": {"company", "club"},
    "sells_to_us_federal": {"yes", "no"},
    "uptime_critical": {"yes", "no"},
}
# Extra extractor fields that fill a spec after a fixed factor.
ALIASES: dict[str, tuple[str, float, str]] = {
    "wheel_diameter_mm": ("wheel_radius_mm", 0.5, "drive wheel diameter (use this, not the "
                          "radius field, when the text gives a diameter)"),
}  # fmt: skip

PROMPT = """\
A robotics team answered four open questions about themselves and their robot. Extract only what
their text states. Their answers are between the markers.

<answers>
{text}
</answers>

Fill `facts` with these, one item each, only when the text states it:
{facts}

Fill `numbers` with these, one item each, only when the text states it:
{numbers}

Rules:
- quote = the words from the answers that state it, copied character for character. Keep it
  short: the phrase with the value, not the whole sentence.
- For `numbers`: value = the number exactly as written in the quote, unit = the unit exactly as
  written (for example "kg", "lb", "mm", "in", "m/s", "mph", "degrees", "%", "V", "weeks"). Do
  not convert units and do not do arithmetic. A number written as a word ("four motors") is
  given as its digits (4).
- Never guess, infer a number, or fill a typical value. Leave out anything not stated.
"""


def response_schema(fields: tuple[SpecField, ...]) -> dict[str, Any]:
    numbers = [f.id for f in fields] + list(ALIASES) + list(COMPANY_NUMBERS)

    def items(names: list[str], value_type: str, extra: dict[str, Any]) -> dict[str, Any]:
        props = {
            "field": {"type": "string", "enum": names},
            "value": {"type": value_type},
            "quote": {"type": "string"},
        } | extra
        return {
            "type": "array",
            "items": {"type": "object", "properties": props, "required": list(props)},
        }

    return {
        "type": "object",
        "properties": {
            "facts": items(list(COMPANY_TEXT), "string", {}),
            "numbers": items(numbers, "number", {"unit": {"type": "string"}}),
        },
        "required": ["facts", "numbers"],
    }


def prompt(answers: Answers, fields: tuple[SpecField, ...]) -> str:
    facts = "\n".join(f"- {name}: {what}" for name, (_, what) in COMPANY_TEXT.items())
    lines = [f"- {f.id}: {f.label.lower()}" + (f" ({f.hint})" if f.hint else "") for f in fields]
    lines += [f"- {name}: {what}" for name, (_, _, what) in ALIASES.items()]
    lines += [f"- {name}: {label.lower()}" for name, (label, _) in COMPANY_NUMBERS.items()]
    return PROMPT.format(text=answers.text(), facts=facts, numbers="\n".join(lines))


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty"
).split()


def _numbers_in(text: str) -> list[float]:
    """Every number the text states: digits ("1,200", "0.5") and the words zero to twenty."""
    digits = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    words = [float(_WORDS.index(w)) for w in re.findall(r"[a-z]+", text.lower()) if w in _WORDS]
    return digits + words


def convert(value: float, unit: str, quantity: Quantity) -> float | None:
    key = re.sub(r"\s+", "", unit.lower()).rstrip(".")
    if quantity == "plain":
        return value
    if quantity == "angle" and key in ("%", "percent", "%grade"):
        return math.degrees(math.atan(value / 100))  # a grade in percent is rise over run
    factor = UNITS[quantity].get(key)
    return None if factor is None else value * factor


def in_range(value: float, field: SpecField) -> bool:
    if field.integer and not float(value).is_integer():
        return False
    if value < 0 or (value == 0 and not field.allow_zero):
        return False
    return field.max is None or value <= field.max


def confirm(
    raw: dict[str, Any], answers: Answers, fields: tuple[SpecField, ...]
) -> tuple[list[CompanyFact], list[Found], list[str]]:
    """(company facts, spec values, what was dropped and why)."""
    text = _norm(answers.text())
    by_id = {f.id: f for f in fields}
    company: list[CompanyFact] = []
    specs: list[Found] = []
    dropped: list[str] = []
    seen: set[str] = set()

    def quoted(name: str, quote: str) -> bool:
        if name in seen:
            return False
        if not _norm(quote) or _norm(quote) not in text:
            dropped.append(f"{name}: the quote is not in your answers")
            return False
        return True

    for item in raw.get("facts", []):
        name, value, quote = (
            item.get("field"),
            str(item.get("value", "")).strip(),
            item.get("quote", ""),
        )
        if name not in COMPANY_TEXT or not value or not quoted(name, quote):
            continue
        if name in _CHOICES and value.lower() not in _CHOICES[name]:
            dropped.append(f"{name}: {value!r} is not one of {sorted(_CHOICES[name])}")
            continue
        if name in ("deploy_countries", "final_assembly_country"):
            codes = [c.strip().upper() for c in value.split(",") if c.strip()]
            if not codes or any(not re.fullmatch(r"[A-Z]{2}", c) for c in codes):
                dropped.append(f"{name}: {value!r} is not a list of two-letter country codes")
                continue
            value = ", ".join(codes if name == "deploy_countries" else codes[:1])
        elif name in _CHOICES:
            value = value.lower()
        seen.add(name)
        company.append(
            CompanyFact(field=name, label=COMPANY_TEXT[name][0], value=value, quote=quote)
        )

    for item in raw.get("numbers", []):
        name, quote, unit = item.get("field"), item.get("quote", ""), str(item.get("unit", ""))
        try:
            written = float(item.get("value"))
        except (TypeError, ValueError):
            continue
        target, factor = (ALIASES[name][0], ALIASES[name][1]) if name in ALIASES else (name, 1.0)
        if target not in by_id and name not in COMPANY_NUMBERS:
            continue
        if not quoted(target, quote):
            continue
        if not any(math.isclose(written, n) for n in _numbers_in(quote)):
            dropped.append(f"{target}: {written:g} is not in the quote “{quote}”")
            continue
        quantity = COMPANY_NUMBERS[name][1] if name in COMPANY_NUMBERS else by_id[target].quantity
        value = convert(written, unit, quantity)
        if value is None:
            dropped.append(f"{target}: unit {unit!r} is not one we convert")
            continue
        value = round(value * factor, 4)
        if name in COMPANY_NUMBERS:
            if value <= 0:
                continue
            seen.add(name)
            shown = f"{value:g} days" if name == "need_by_days" else f"${value:,.0f}"
            company.append(
                CompanyFact(field=name, label=COMPANY_NUMBERS[name][0], value=shown, quote=quote)
            )
            continue
        if not in_range(value, by_id[target]):
            dropped.append(f"{target}: {value:g} is out of range")
            continue
        seen.add(target)
        specs.append(Found(field=target, value=value, source="answer", evidence=quote))
    return company, specs, dropped
