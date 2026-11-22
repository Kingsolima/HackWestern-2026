"""TRIAGE (docs/design/04 section 3, 07 section 4): decide per discovered URL whether its specs
can be read from the fetched page (cheap: Fetch + Gemini extraction), whether the TinyAgent
must click through it (paid agent run, live tile), or whether it is not worth anything.

Gemini Decision 1 answers one choice question per page with calibrated probabilities; code
composes the route. The model can never route to `readable` on its own: the fetched text must
also carry a torque value with a unit, because pages that fill their spec tables with
JavaScript (Teknic) arrive from Fetch with empty cells.
"""

import re
from typing import Literal

from pydantic import BaseModel

TriageLabel = Literal[
    "readable_specs", "needs_interaction", "not_a_product_page", "blocked_or_captcha"
]
Route = Literal["readable", "needs_interaction", "dead"]

CONFIDENCE = 0.8


class TriageInput(BaseModel):
    url: str
    fetch_ok: bool
    text: str | None = None
    decision: dict[TriageLabel, float] | None = None  # Decision 1 probabilities; None = call failed


def route_page(page: TriageInput) -> Route:
    """Contract (tests/test_triage_core.py):
    - fetch failed, no text, or no Decision 1 answer -> needs_interaction (safe default: a
      browser agent may get through where a plain fetch did not).
    - top label below CONFIDENCE -> needs_interaction.
    - top label not_a_product_page (>= CONFIDENCE) -> dead.
    - top label blocked_or_captcha (>= CONFIDENCE) -> needs_interaction (the agent retries with
      stealth and a US proxy).
    - top label needs_interaction (>= CONFIDENCE) -> needs_interaction.
    - top label readable_specs (>= CONFIDENCE) -> readable only if the text contains a number
      followed by a torque unit (oz-in, N-m / Nm / N·m, mNm, lb-in, kgf-cm; case-insensitive
      except the N, optional space or hyphen variants); otherwise needs_interaction.
    """
    if not page.fetch_ok or not page.text or not page.decision:
        return "needs_interaction"
    label, p = max(page.decision.items(), key=lambda item: item[1])
    if p < CONFIDENCE:
        return "needs_interaction"
    if label == "not_a_product_page":
        return "dead"
    if label == "readable_specs" and _TORQUE_VALUE.search(page.text):
        return "readable"
    return "needs_interaction"


# A number, then a torque unit. The lookahead rejects squared units (oz-in² is rotor inertia)
# and longer words that merely start like a unit. N stays capital so "905 nm" (a laser
# wavelength) is not read as newton-metres.
_SEP = r"[\s.\-·*]?"
_TORQUE_VALUE = re.compile(
    rf"\d\s*(?:oz{_SEP}in|m?(?-i:N){_SEP}m|lbf?{_SEP}in|kgf?{_SEP}cm)(?![\w²³^])",
    re.IGNORECASE,
)


class Lead(BaseModel):
    """A page discovery found for the swap line, with its triage route once known."""

    url: str
    domain: str
    title: str | None = None
    route: Route | None = None
    text: str | None = None
