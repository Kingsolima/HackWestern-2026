"""Verifier (HANDOFF-v3 §7, docs/design/04-architecture.md VERIFY). Deterministic. Owner 2.

Tygo writes `classify_outcome` and `verify_claim` by hand; tests/test_verifier_todo.py holds
the expected behaviour as xfail tests. Only this module may mark a Claim verified.
"""

from typing import Any, Literal

from app.schemas import Claim

Outcome = Literal["success", "blocked", "not_found", "auth_required", "incomplete", "error"]


def classify_outcome(run: dict[str, Any]) -> Outcome:
    """Map a TinyAgent COMPLETE event / run object to an outcome.

    COMPLETED with result.status != success, an all-null result, "access denied"/CAPTCHA
    text, or FAILED must map to blocked | not_found | auth_required | incomplete | error.
    Only a clean result is success.
    """
    raise NotImplementedError("Tygo implements (HANDOFF-v3 §7)")


def verify_claim(claim: Claim, page_text: str) -> Claim:
    """Check a claim against freshly fetched html/PDF text.

    Normalize whitespace and thousands separators, find the quote, check the number in the
    quote equals claim.raw_value, then return a copy with verified/verify_method set.
    """
    raise NotImplementedError("Tygo implements (HANDOFF-v3 §7)")


OriginTier = Literal["T1", "T2", "T3", "rejected", "none"]


def origin_tier(origin_quote: str | None, country: str | None) -> OriginTier:
    """Code rules for the origin tier (07-agent-architecture.md). Decision 1 may only lower it.

    "Designed in USA" or an HQ address alone must never reach T1/T2.
    """
    raise NotImplementedError("Tygo implements (HANDOFF-v3 §7)")
