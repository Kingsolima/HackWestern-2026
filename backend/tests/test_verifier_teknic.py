"""Verifier on real data: Omar's live TinyAgent run on Teknic CPM-SDSK-2310D-RLN and fresh
TinyFetch html of the model page (recorded Nov 21, 2026; commit 3e8f9a3 on swap-finder-swarm).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agents.verifier import origin_class, origin_tier, verify_claim
from app.schemas import AgentMotorCandidate, Claim, Source

FIXTURES = Path(__file__).parent / "fixtures" / "teknic"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


CANDIDATE = AgentMotorCandidate.model_validate(load("agent_run.json")["events"][-1]["result"])


def page_text(name: str) -> str:
    return load(name)["response"]["results"][0]["text"]


def verified_fields(text: str) -> set[str]:
    fields = set()
    for spec in CANDIDATE.specs:
        claim = Claim(
            id=spec.name,
            candidate_id=CANDIDATE.part_number or "",
            field=spec.name,
            raw_value=f"{spec.value:g}",
            raw_unit=spec.unit,
            quote=spec.quote,
            source=Source(
                url=spec.source_url, kind="page", fetched_at=datetime.now(UTC), via="tinyfetch"
            ),
            extracted_by="tinyagent",
        )
        if verify_claim(claim, text, "html_quote").verified:
            fields.add(spec.name)
    return fields


def test_specs_on_the_page_verify_and_the_garbled_torque_does_not():
    # The agent quoted "13 oz-in (1.8 N-m)": 13 oz-in is 0.09 N-m, and neither text is on
    # the page. Max speed "4,000 RPM" is not on the page either.
    assert verified_fields(page_text("fetch_tables.json")) == {
        "supply_voltage_min",
        "supply_voltage_max",
        "body_length",
        "shaft_diameter",
        "price",
    }


def test_default_html_fetch_misses_the_spec_table():
    assert verified_fields(page_text("fetch_default.json")) == set()


@pytest.mark.parametrize("model_specific", [True, False])
def test_teknic_about_page_quote_is_us_made_but_not_model_specific(model_specific):
    assert CANDIDATE.origin_quote == "Teknic designs and builds products in the USA."
    cls = origin_class(CANDIDATE.origin_quote)
    assert cls == "us_made_site_unstated"
    assert origin_tier(cls, model_specific) == ("T1" if model_specific else "T3")
