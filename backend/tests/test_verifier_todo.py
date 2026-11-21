"""Expected verifier behaviour (HANDOFF-v3 §7). Tygo implements app/agents/verifier.py.

These are strict xfail: they pass CI while unimplemented, and turn into failures once the
code works, so remove the marker as each one goes green.
"""

from datetime import UTC, datetime

import pytest

from app.agents.verifier import classify_outcome, origin_tier, verify_claim
from app.schemas import Claim, Source

TODO = pytest.mark.xfail(strict=True, reason="Tygo implements (HANDOFF-v3 §7)")

URL = "https://teknic.com/model-info/CPM-SDSK-2311S-RLN/"


def claim(field: str, raw_value: str, quote: str, unit: str | None = None) -> Claim:
    return Claim(
        candidate_id="teknic-1",
        field=field,
        raw_value=raw_value,
        raw_unit=unit,
        quote=quote,
        source=Source(url=URL, kind="page", fetched_at=datetime.now(UTC), via="tinyfetch"),
        extracted_by="tinyagent",
    )


@TODO
def test_completed_run_with_all_nulls_is_not_success():
    run = {
        "type": "COMPLETE",
        "status": "COMPLETED",
        "result": {
            "status": "success",
            "reason": "",
            "manufacturer": None,
            "part_number": None,
            "specs": [],
            "country_of_origin": None,
            "product_url": None,
        },
    }
    assert classify_outcome(run) != "success"


@TODO
def test_captcha_text_is_blocked():
    run = {
        "type": "COMPLETE",
        "status": "COMPLETED",
        "result": {"status": "success", "reason": "Page showed a CAPTCHA, access denied"},
    }
    assert classify_outcome(run) == "blocked"


@TODO
def test_failed_run_is_error():
    assert classify_outcome({"type": "COMPLETE", "status": "FAILED", "result": None}) == "error"


@TODO
def test_quote_present_and_number_matches_is_verified():
    page = "<td>Price</td><td>$1,045.00</td>"
    out = verify_claim(claim("price", "1045", "Price $1,045.00", "USD"), page)
    assert out.verified and out.verify_method == "html_quote"


@TODO
def test_quote_present_but_number_differs_is_rejected():
    # promo vs regular price: the quote text is on the page, but with another number
    page = "<p>Regular price $1,045.00</p><p>Sale $899.00</p>"
    out = verify_claim(claim("price", "899", "Regular price $899.00", "USD"), page)
    assert not out.verified


@TODO
def test_quote_split_across_tags_is_found():
    page = "<tr><th>Peak Torque</th>\n  <td><span>3.18</span> N-m</td></tr>"
    out = verify_claim(claim("peak_torque", "3.18", "Peak Torque 3.18 N-m", "N-m"), page)
    assert out.verified


@TODO
def test_designed_in_usa_is_not_us_made():
    assert origin_tier("Designed in USA", "US") not in ("T1", "T2")
