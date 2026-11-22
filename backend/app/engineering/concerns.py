"""What the customer wants to avoid, and which parts may depend on it.

The model does two jobs here and neither is a verdict:
1. It splits the customer's own sentence into separate concerns. Code keeps a concern only when
   its quote is in that sentence.
2. For a material concern it says whether a part of that class typically depends on the
   material ("a servo motor has permanent magnets"). That is general knowledge about the class,
   not a fact about the product, so it is carried as INFERRED all the way to the screen.

Scores and actions are decided by code in engineering/priority.py.
"""

import re
from typing import Any

from app.schemas import BomLine, Concern, Dependency

CONCERNS_PROMPT = """\
A robotics team told us what it wants to avoid in its supply chain. Their words:
"{avoid}"

Their parts list (id: part):
{parts}

Return two lists.

concerns: every separate thing they say they want to avoid, and nothing they did not say.
- kind: "material" for a material or component technology (for example rare-earth magnets,
  cobalt cells), "country" for anything made in a country, "supplier" for a named company or
  a kind of supplier.
- label: a short name for it.
- country: the ISO 3166 two-letter code when the concern names a country or nationality,
  otherwise null.
- quote: their words for it, copied character for character from the sentence above.

dependencies: for every "material" concern and every part in the list, whether a part of that
class typically depends on that material.
- depends: "likely", "unlikely", or "unknown" when the part name does not say enough.
- why: one short sentence.
This is general engineering knowledge about the kind of part. It is not a claim about the
specific product, and it will be shown to the team as inferred, not verified.
"""

CONCERNS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concerns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["material", "country", "supplier"]},
                    "label": {"type": "string"},
                    "country": {"type": "string", "nullable": True},
                    "quote": {"type": "string"},
                },
                "required": ["id", "kind", "label", "quote"],
            },
        },
        "dependencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_id": {"type": "string"},
                    "concern_id": {"type": "string"},
                    "depends": {"type": "string", "enum": ["likely", "unlikely", "unknown"]},
                    "why": {"type": "string"},
                },
                "required": ["line_id", "concern_id", "depends"],
            },
        },
    },
    "required": ["concerns", "dependencies"],
}


def concerns_prompt(avoid: str, bom: list[BomLine]) -> str:
    parts = "\n".join(f"{line.id}: {line.part}" for line in bom)
    return CONCERNS_PROMPT.format(avoid=avoid, parts=parts)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def confirm_concerns(
    raw: dict[str, Any], avoid: str, bom: list[BomLine]
) -> tuple[list[Concern], list[Dependency]]:
    """Keep what code can stand behind: a concern whose quote is in the customer's sentence, a
    country that is a two-letter code, a dependency that names a real line and a kept material
    concern. Anything else is dropped."""
    said = _norm(avoid)
    concerns: list[Concern] = []
    for item in raw.get("concerns", []):
        if not isinstance(item, dict):
            continue
        quote, label = str(item.get("quote", "")), str(item.get("label", "")).strip()
        kind = item.get("kind")
        if not label or kind not in ("material", "country", "supplier"):
            continue
        if not _norm(quote) or _norm(quote) not in said:
            continue
        country = str(item.get("country") or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", country):
            country = ""
        if kind == "country" and not country:
            continue
        concerns.append(
            Concern(
                id=str(item.get("id") or f"c{len(concerns) + 1}"),
                kind=kind,
                label=label,
                country=country or None,
                quote=quote.strip(),
            )
        )
    materials = {c.id for c in concerns if c.kind == "material"}
    lines = {line.id for line in bom}
    deps: dict[tuple[str, str], Dependency] = {}
    for item in raw.get("dependencies", []):
        if not isinstance(item, dict):
            continue
        line_id, concern_id = str(item.get("line_id")), str(item.get("concern_id"))
        depends = item.get("depends")
        if line_id not in lines or concern_id not in materials:
            continue
        if depends not in ("likely", "unlikely", "unknown"):
            continue
        deps[(line_id, concern_id)] = Dependency(
            line_id=line_id,
            concern_id=concern_id,
            depends=depends,
            why=str(item.get("why") or "").strip()[:300],
        )
    return concerns, list(deps.values())
