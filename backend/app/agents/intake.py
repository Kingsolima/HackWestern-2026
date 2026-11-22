"""INTAKE (docs/BUILD-PLAN-v4.md section 3): facts about a company read from its own pages.

Gemini Flash reads one fetched page and proposes facts, each with the exact sentence that
states it. A fact counts only when verify_claim finds that sentence in the same page text; the
UI shows the quote, so a reader can judge whether it supports the value. Club projects have no
pages to read: their facts are what the club stated in the project file.
"""

import re
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from app.agents.verifier import verify_claim
from app.schemas import Claim, Fact, FactField, ProjectFacts, Source

# Facts a company's public pages can state. Budget and deadline are only ever stated by a team.
PAGE_FIELDS: tuple[FactField, ...] = ("sells_to_us_federal", "deploy_countries", "uptime_critical")

INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(PAGE_FIELDS)},
                    "value": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["field", "value", "quote"],
            },
        }
    },
    "required": ["facts"],
}

INTAKE_PROMPT = """\
You read one page from {company}'s own website about {robot}. List only facts this page states
explicitly, each with a quote: the sentence or phrase exactly as it appears in the page text,
character for character, with no added words.

Fields:
- deploy_countries: a country where {robot} is deployed or sold, as an ISO 3166 two-letter code
  (US, CA, DE, ...). One fact per country. A named customer is not a country unless the page
  says where the robot works for it.
- uptime_critical: "true" only if the page says downtime or uptime matters to its customers.
- sells_to_us_federal: "true" only if the page says {robot} is sold to or used by a US federal
  agency or the US military.

Leave a field out when the page does not state it. Never infer, never guess.

Page URL: {url}

Page text:
{text}
"""

_ISO2 = re.compile(r"^[A-Z]{2}$")


class _Proposed(BaseModel):
    field: FactField
    value: str
    quote: str


def page_facts(
    raw: object, project_id: str, url: str, text: str, run: str
) -> tuple[list[Fact], list[Claim]]:
    """Flash output for one page -> facts whose quote verifies, plus every claim (verified or not)
    for the event stream. Malformed rows and values outside each field's form are dropped."""
    rows = raw.get("facts", []) if isinstance(raw, dict) else []
    now = datetime.now(UTC)
    facts: list[Fact] = []
    claims: list[Claim] = []
    for i, row in enumerate(rows):
        try:
            p = _Proposed.model_validate(row)
        except ValidationError:
            continue
        value = _clean(p.field, p.value)
        if value is None or p.field not in PAGE_FIELDS:
            continue
        claim = verify_claim(
            Claim(
                id=f"{run}:{i}",
                candidate_id=f"project:{project_id}",
                field=p.field,
                raw_value=value,
                raw_unit=None,
                quote=p.quote,
                source=Source(url=url, kind="page", fetched_at=now, via="tinyfetch"),
                extracted_by="gemini_text",
            ),
            text,
            "html_quote",
        )
        claims.append(claim)
        if claim.verified:
            facts.append(
                Fact(
                    field=p.field,
                    value=value,
                    basis="verified",
                    quote=p.quote,
                    source_url=url,
                    claim_id=claim.id,
                )
            )
    return facts, claims


def _clean(field: FactField, value: str) -> str | None:
    v = value.strip()
    if field == "deploy_countries":
        v = v.upper()
        return v if _ISO2.match(v) else None
    v = v.lower()
    return v if v in ("true", "false") else None


def merge_facts(stated: ProjectFacts, verified: list[Fact]) -> tuple[ProjectFacts, list[Fact]]:
    """Stated facts first, then verified facts on top: a verified value replaces a stated one,
    countries are the union. Returns the facts and one Fact record per value used."""
    facts = stated.model_copy(deep=True)
    used: list[Fact] = [
        Fact(field=name, value=_text(getattr(stated, name)), basis="stated")
        for name in ProjectFacts.model_fields
        if getattr(stated, name) not in (None, [])
    ]
    for f in verified:
        if f.field == "deploy_countries":
            if f.value not in facts.deploy_countries:
                facts.deploy_countries.append(f.value)
                used.append(f)
            continue
        if any(u.field == f.field and u.basis == "verified" for u in used):
            continue  # the first verified value of a field stands
        setattr(facts, f.field, f.value == "true")
        used = [u for u in used if u.field != f.field]
        used.append(f)
    return facts, used


def _text(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
