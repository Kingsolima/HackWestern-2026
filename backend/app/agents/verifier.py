"""Verifier: the only code that turns raw claims into facts (docs/design/07 section 2).

Deterministic. Two parts:
- run outcome and claim verification (`classify_outcome`, `verify_claim`), and
- origin tier rules (`origin_class`, `origin_tier`, `lower_tier`). Decision 1 may suggest a
  class; the final tier is `lower_tier(code tier, model tier)`, so a model can only lower it.
"""

import html
import re
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from app.schemas import (
    AgentRunResult,
    Candidate,
    Claim,
    OriginEvidence,
    OriginTier,
    Outcome,
    VerifyMethod,
)


def classify_outcome(run: AgentRunResult) -> Outcome:
    """Map a finished TinyAgent run to an Outcome. Only a clean result is `success`.

    Contract (tests/test_verifier_core.py):
    - PENDING or RUNNING is not finished: raise ValueError (never classify a live run).
    - FAILED or CANCELLED: `profile_hint_reason` bot_challenge -> blocked, auth_wall ->
      auth_required, otherwise error.
    - COMPLETED: bot-challenge / access-denied / CAPTCHA wording in `page_text` -> blocked;
      no result -> incomplete; result `status` other than success -> that status;
      every data field (all keys but status and reason) null or empty -> incomplete;
      otherwise success.
    """
    if run.tf_status == "PENDING" or run.tf_status == "RUNNING":
        raise ValueError(f"run {run.run_id} is still {run.tf_status}")
    if run.tf_status == "FAILED" or run.tf_status == "CANCELLED":
        if run.profile_hint_reason == "bot_challenge":
            return "blocked"
        elif run.profile_hint_reason == "auth_wall":
            return "auth_required"
        else:
            return "error"
    if run.page_text and _BOT_WALL.search(run.page_text):
        return "blocked"
    if run.result is None:
        return "incomplete"
    status = run.result.get("status")
    if status != "success":
        return status if status in _AGENT_FAILURES else "incomplete"
    data = [v for k, v in run.result.items() if k not in ("status", "reason")]
    if all(v in (None, [], "") for v in data):
        return "incomplete"
    return "success"


_BOT_WALL = re.compile(
    r"access denied|captcha|verify you are human|checking if the site connection is secure"
    r"|are you a robot|unusual traffic",
    re.I,
)
_AGENT_FAILURES: frozenset[Outcome] = frozenset(
    {"blocked", "not_found", "auth_required", "incomplete"}
)


def verify_claim(claim: Claim, text: str, method: VerifyMethod) -> Claim:
    """Check a claim against independently fetched page html or PDF text.

    Returns a copy; never mutates `claim`. Verified only if:
    - the claim was not read from an image (`extracted_by` gemini_vision is never verified),
    - the normalized quote occurs in the normalized text, and
    - the normalized `raw_value` equals a number inside the normalized quote, compared as
      decimals ("0.5" == "0.50"; a decimal comma "0,50" reads as 0.50).
    Normalization: html tags and colons become spaces, unescape entities (incl. &nbsp;), remove
    thousands separators ("1,200" -> "1200"), collapse whitespace, casefold.
    A non-numeric `raw_value` (e.g. country_of_origin "US") needs only the quote match; the
    origin rules read the quote itself.
    Verified -> `verified=True, verify_method=method`; else `verified=False, verify_method="none"`.
    """
    quote = _normalize(claim.quote)
    verified = (
        claim.extracted_by != "gemini_vision"
        and quote != ""
        and quote in _normalize(text)
        and _value_in_quote(_normalize(claim.raw_value), quote)
    )
    return claim.model_copy(
        update={"verified": verified, "verify_method": method if verified else "none"}
    )


_TAG = re.compile(r"<[^>]*>")
_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _normalize(text: str) -> str:
    """Tags become spaces, so a tag inside a word fails the match instead of gluing words.
    Colons become spaces: agents write "Length: 3.34 in" where the page has two table cells."""
    text = html.unescape(_TAG.sub(" ", text)).replace(":", " ")
    text = _THOUSANDS_COMMA.sub("", text)
    return " ".join(text.split()).casefold()


def _value_in_quote(value: str, quote: str) -> bool:
    if not _NUMBER.fullmatch(value):
        return True
    return any(_decimal(n) == _decimal(value) for n in _NUMBER.findall(quote))


def _decimal(number: str) -> Decimal:
    return Decimal(number.replace(",", "."))


_CANONICAL = re.compile(
    r"<link\b[^>]*\brel=[\"']?canonical[\"']?[^>]*\bhref=[\"']([^\"']+)[\"']"
    r"|<link\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*\brel=[\"']?canonical",
    re.I,
)


def same_page(a: str, b: str) -> bool:
    """Same host and path; query, fragment, scheme and a trailing slash are ignored."""

    def key(url: str) -> tuple[str, str]:
        parts = urlsplit(url.strip())
        return (parts.hostname or "").removeprefix("www."), parts.path.rstrip("/")

    return key(a) == key(b)


def canonical_url(html_text: str) -> str | None:
    match = _CANONICAL.search(html_text)
    return html.unescape(match.group(1) or match.group(2)) if match else None


OriginClass = Literal[
    "made_at_named_us_plant",
    "us_made_site_unstated",
    "assembled_in_us",
    "designed_in_us",
    "us_hq_only",
    "foreign",
    "not_origin",
]

_US = (
    r"(?:the\s+)?(?:(?-i:U\.?\s?S\.?(?:A\.?)?)|usa|u\.s\.a\.?"
    r"|united\s+states(?:\s+of\s+america)?|america)"
)
_STATES = (
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|"
    "hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|"
    "massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|"
    "new\\s+hampshire|new\\s+jersey|new\\s+mexico|new\\s+york|north\\s+carolina|north\\s+dakota|"
    "ohio|oklahoma|oregon|pennsylvania|rhode\\s+island|south\\s+carolina|south\\s+dakota|"
    "tennessee|texas|utah|vermont|virginia|washington|west\\s+virginia|wisconsin|wyoming"
)
_STATE_ABBR = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|"
    "NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY"
)
_US_PLACE = rf"(?:\b{_US}(?!\w)|\b(?:{_STATES})\b|,\s?(?-i:{_STATE_ABBR})\b)"
_MAKE = r"\b(?:made|makes|manufacture[ds]?|produce[ds]?|built|builds?|fabricated)\b"
_PLANT = r"\b(?:plant|plants|facility|facilities|factory|factories)\b"
_FOREIGN = (
    "china|prc|taiwan|japan|korea|vietnam|mexico|germany|india|malaysia|thailand|philippines|"
    "indonesia|singapore|canada|italy|france|switzerland|czech\\s+republic|poland|hungary|"
    "israel|united\\s+kingdom|uk|england"
)

_RULES: list[tuple[OriginClass, re.Pattern[str]]] = [
    (
        "foreign",
        re.compile(
            rf"(?:{_MAKE}|\bassembled\b)[^.]*?\bin\s+(?:{_FOREIGN})\b"
            rf"|\bcountry\s+of\s+origin\s*:?\s*(?:{_FOREIGN})\b",
            re.I,
        ),
    ),
    (
        "made_at_named_us_plant",
        re.compile(
            rf"{_MAKE}[^.]*?{_US_PLACE}[^.]*?{_PLANT}|{_MAKE}[^.]*?{_PLANT}[^.]*?{_US_PLACE}",
            re.I,
        ),
    ),
    (
        "us_made_site_unstated",
        re.compile(
            rf"{_MAKE}(?:\s+\w+){{0,3}}?\s+in\s+{_US}(?!\w)|\b(?:usa|american)-made\b"
            rf"|\bcountry\s+of\s+origin\s*:?\s*{_US}(?!\w)",
            re.I,
        ),
    ),
    ("assembled_in_us", re.compile(rf"\bassembled\s+in\s+{_US}(?!\w)", re.I)),
    ("designed_in_us", re.compile(rf"\b(?:designed|engineered)\s+in\s+{_US}(?!\w)", re.I)),
]


def origin_class(quote: str) -> OriginClass:
    """Strongest origin statement the quote's own words support. Foreign wins over any US claim."""
    for cls, pattern in _RULES:
        if pattern.search(quote):
            return cls
    return "not_origin"


def origin_tier(cls: OriginClass, model_specific: bool) -> OriginTier:
    """Code rule (04 section 10.9). model_specific: the quote is on the model's own page or a
    datasheet that names the model."""
    match cls:
        case "made_at_named_us_plant":
            return "T1" if model_specific else "T2"
        case "us_made_site_unstated":
            return "T1" if model_specific else "T3"
        case "assembled_in_us" | "us_hq_only":
            return "T3"
        case "designed_in_us" | "foreign":
            return "rejected"
        case "not_origin":
            return "none"


_TIER_RANK: dict[OriginTier, int] = {"rejected": 0, "none": 1, "T3": 2, "T2": 3, "T1": 4}


def lower_tier(a: OriginTier, b: OriginTier) -> OriginTier:
    return a if _TIER_RANK[a] <= _TIER_RANK[b] else b


_US_CLASSES: frozenset[OriginClass] = frozenset(
    {"made_at_named_us_plant", "us_made_site_unstated", "assembled_in_us", "us_hq_only"}
)


def origin_evidence(candidate: Candidate) -> OriginEvidence:
    """Tier from the candidate's verified origin claim by code rules. The quote is model
    specific when it sits on the candidate's own product page."""
    claim = next(
        (c for c in candidate.claims if c.field == "country_of_origin" and c.verified), None
    )
    if claim is None:
        return OriginEvidence(country=None, tier="none", claim_id=None)
    cls = origin_class(claim.quote)
    on_model_page = candidate.product_url is not None and same_page(
        claim.source.url, candidate.product_url
    )
    country = "US" if cls in _US_CLASSES else claim.raw_value
    return OriginEvidence(country=country, tier=origin_tier(cls, on_model_page), claim_id=claim.id)
