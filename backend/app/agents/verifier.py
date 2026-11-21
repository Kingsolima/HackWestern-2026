"""Verifier: the only code that turns raw claims into facts (docs/design/07 section 2).

Deterministic. Two parts:
- run outcome and claim verification (`classify_outcome`, `verify_claim`), and
- origin tier rules (`origin_class`, `origin_tier`, `lower_tier`). Decision 1 may suggest a
  class; the final tier is `lower_tier(code tier, model tier)`, so a model can only lower it.
"""

import re
from typing import Literal

from app.schemas import AgentRunResult, Claim, OriginTier, Outcome, VerifyMethod


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
    raise NotImplementedError("Tygo: core of chunk 1")


def verify_claim(claim: Claim, text: str, method: VerifyMethod) -> Claim:
    """Check a claim against independently fetched page html or PDF text.

    Returns a copy; never mutates `claim`. Verified only if:
    - the claim was not read from an image (`extracted_by` gemini_vision is never verified),
    - the normalized quote occurs in the normalized text, and
    - the normalized `raw_value` equals a number inside the normalized quote.
    Normalization: drop html tags, unescape entities (incl. &nbsp;), collapse whitespace,
    remove thousands separators ("1,200" -> "1200").
    A non-numeric `raw_value` (e.g. country_of_origin "US") needs only the quote match; the
    origin rules read the quote itself.
    Verified -> `verified=True, verify_method=method`; else `verified=False, verify_method="none"`.
    """
    raise NotImplementedError("Tygo: core of chunk 1")


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
_MAKE = r"\b(?:made|manufactured|produced|built|build|fabricated)\b"
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
        re.compile(rf"{_MAKE}\s+in\s+{_US}(?!\w)|\b(?:usa|american)-made\b", re.I),
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
