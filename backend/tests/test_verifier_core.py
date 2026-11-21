"""Tygo's chunk 1 core: classify_outcome and verify_claim. These fail until both are written.

Spec: docs/HANDOFF-v3.md section 7, docs/design/04 section 5, docs/design/05 section 6.
"""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.agents.verifier import classify_outcome, verify_claim
from app.config import settings
from app.main import app
from app.schemas import AgentRunResult, Claim, Source

# --- classify_outcome ---------------------------------------------------------------------

CLEAN = {
    "status": "success",
    "reason": "found specs",
    "manufacturer": "Teknic",
    "part_number": "CPM-SDSK-2321S-RLN",
    "motor_type": "servo_integrated",
    "nema_frame": "23",
    "specs": [],
    "country_of_origin": None,
    "origin_quote": None,
    "origin_source_url": None,
    "product_url": "https://teknic.com/x",
    "datasheet_url": None,
}
ALL_NULL = {k: ([] if k == "specs" else None) for k in CLEAN} | {
    "status": "success",
    "reason": "done",
}


def run(tf_status="COMPLETED", result=CLEAN, **kw) -> AgentRunResult:
    return AgentRunResult(run_id="r1", tf_status=tf_status, result=result, **kw)


def test_clean_completed_run_is_success():
    assert classify_outcome(run()) == "success"


def test_completed_with_all_null_data_is_incomplete():
    assert classify_outcome(run(result=ALL_NULL)) == "incomplete"


def test_completed_without_result_is_incomplete():
    assert classify_outcome(run(result=None)) == "incomplete"


@pytest.mark.parametrize("status", ["blocked", "not_found", "auth_required", "incomplete"])
def test_completed_with_agent_reported_failure_keeps_it(status):
    assert classify_outcome(run(result=CLEAN | {"status": status})) == status


def test_unknown_agent_status_is_incomplete():
    assert classify_outcome(run(result=CLEAN | {"status": "partial"})) == "incomplete"


@pytest.mark.parametrize(
    "page_text",
    [
        "Access Denied. You don't have permission to access this server.",
        "Please verify you are human by completing the CAPTCHA below",
        "Checking if the site connection is secure. Cloudflare Ray ID: 8f1",
    ],
)
def test_completed_on_a_bot_wall_is_blocked(page_text):
    assert classify_outcome(run(page_text=page_text)) == "blocked"


@pytest.mark.parametrize(
    ("hint", "outcome"),
    [(None, "error"), ("bot_challenge", "blocked"), ("auth_wall", "auth_required")],
)
@pytest.mark.parametrize("tf_status", ["FAILED", "CANCELLED"])
def test_failed_runs(tf_status, hint, outcome):
    got = classify_outcome(run(tf_status=tf_status, result=None, profile_hint_reason=hint))
    assert got == outcome


@pytest.mark.parametrize("tf_status", ["PENDING", "RUNNING"])
def test_unfinished_run_is_never_classified(tf_status):
    with pytest.raises(ValueError):
        classify_outcome(run(tf_status=tf_status, result=None))


# --- verify_claim -------------------------------------------------------------------------


def claim(raw_value: str, quote: str, extracted_by="tinyagent", field="price") -> Claim:
    return Claim(
        id="c1",
        candidate_id="m1",
        field=field,
        raw_value=raw_value,
        raw_unit=None,
        quote=quote,
        source=Source(url="https://x", kind="page", fetched_at=datetime.now(UTC), via="tinyfetch"),
        extracted_by=extracted_by,
    )


def test_quote_and_number_match():
    page = "<p>Continuous torque: 0.50 N-m</p>"
    got = verify_claim(claim("0.50", "Continuous torque: 0.50 N-m"), page, "html_quote")
    assert (got.verified, got.verify_method) == (True, "html_quote")


def test_quote_split_across_tags():
    page = "<p>Continuous torque: <b>0.50</b>\n   <span>N-m</span></p>"
    assert verify_claim(claim("0.50", "Continuous torque: 0.50 N-m"), page, "html_quote").verified


def test_thousands_separators_and_nbsp_are_normalized():
    page = "<td>Rated speed:</td><td>3,000&nbsp;rpm</td>"
    assert verify_claim(claim("3000", "Rated speed: 3,000 rpm"), page, "html_quote").verified


def test_promo_vs_regular_price_is_rejected():
    page = "<p>Regular price $299</p><p>Sale price $265</p>"
    got = verify_claim(claim("265", "Regular price $299"), page, "html_quote")
    assert (got.verified, got.verify_method) == (False, "none")


def test_quote_missing_from_page_is_rejected():
    page = "<p>Continuous torque: 0.45 N-m</p>"
    assert not verify_claim(
        claim("0.50", "Continuous torque: 0.50 N-m"), page, "html_quote"
    ).verified


def test_image_read_claims_are_never_verified():
    page = "<p>Continuous torque: 0.50 N-m</p>"
    c = claim("0.50", "Continuous torque: 0.50 N-m", extracted_by="gemini_vision")
    assert not verify_claim(c, page, "html_quote").verified


def test_pdf_text_method_is_recorded():
    text = "Peak torque  1.2 N·m\nContinuous torque 0.5 N·m"
    got = verify_claim(claim("1.2", "Peak torque 1.2 N·m"), text, "pdf_text")
    assert (got.verified, got.verify_method) == (True, "pdf_text")


def test_non_numeric_claim_needs_only_the_quote():
    page = "<footer>Made in USA at our Ohio plant.</footer>"
    c = claim("US", "Made in USA at our Ohio plant.", field="country_of_origin")
    assert verify_claim(c, page, "html_quote").verified


def test_empty_quote_never_verifies():
    c = claim("US", "  ", field="country_of_origin")
    assert not verify_claim(c, "<p>Made in USA</p>", "html_quote").verified


def test_numbers_compare_as_decimals():
    page = "<p>Continuous torque: 0.50 N-m</p>"
    assert verify_claim(claim("0.5", "Continuous torque: 0.50 N-m"), page, "html_quote").verified


def test_decimal_comma_is_not_a_thousands_separator():
    page = "<p>Drehmoment: 0,50 Nm</p>"
    assert not verify_claim(claim("50", "Drehmoment: 0,50 Nm"), page, "html_quote").verified
    assert verify_claim(claim("0.50", "Drehmoment: 0,50 Nm"), page, "html_quote").verified


def test_quote_match_ignores_case():
    page = "<h3>CONTINUOUS TORQUE: 0.50 N-m</h3>"
    assert verify_claim(claim("0.50", "Continuous torque: 0.50 N-m"), page, "html_quote").verified


def test_tags_do_not_glue_numbers_together():
    page = "<td>max 10</td><td>0.5 N-m</td>"
    assert not verify_claim(claim("100.5", "max 100.5 N-m"), page, "html_quote").verified


def test_input_claim_is_not_mutated():
    c = claim("0.50", "Continuous torque: 0.50 N-m")
    verify_claim(c, "<p>Continuous torque: 0.50 N-m</p>", "html_quote")
    assert not c.verified


# --- the fake job end to end (needs verify_claim) -----------------------------------------


def test_fake_job_verifies_three_claims_and_rejects_the_promo_price(monkeypatch):
    monkeypatch.setattr(settings, "replay_speed", 0)
    with TestClient(app) as client:
        job_id = client.post("/api/jobs", json={"mode": "replay"}).json()["job_id"]
        with client.stream("GET", f"/api/jobs/{job_id}/events") as r:
            events = [json.loads(x[5:]) for x in r.iter_lines() if x.startswith("data:")]
        board = client.portal.call(client.app.state.runtime.board.read, job_id, "fact")
    verified = sorted(e["data"]["claim"]["field"] for e in events if e["type"] == "claim_verified")
    rejected = [e["data"]["claim"]["field"] for e in events if e["type"] == "claim_rejected"]
    assert verified == ["continuous_torque", "country_of_origin", "rated_speed"]
    assert rejected == ["price"]
    assert events[-1]["data"]["stage"] == "DONE"
    assert sorted(row.payload["field"] for row in board) == verified
