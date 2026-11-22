"""INTAKE + CRITERIA (docs/BUILD-PLAN-v4.md sections 3 and 5)."""

import json

import httpx
import pytest

from app.agents.intake import merge_facts, page_facts
from app.schemas import Fact, ProjectFacts

PAGE = (
    "# Stretch\n\nStretch is deployed at DHL sites across North America.\n\n"
    "Every hour a robot sits idle is an hour of work that piles up on the dock.\n\n"
    "Now shipping in the **United States** and Canada."
)
URL = "https://bostondynamics.com/products/stretch"


def facts_for(rows):
    return page_facts({"facts": rows}, "p", URL, PAGE, "run")


def test_only_facts_whose_quote_is_on_the_page_count():
    facts, claims = facts_for(
        [
            {
                "field": "uptime_critical",
                "value": "true",
                "quote": "Every hour a robot sits idle is an hour of work",
            },
            {"field": "sells_to_us_federal", "value": "true", "quote": "Trusted by the US Army."},
        ]
    )
    assert [(f.field, f.value, f.basis) for f in facts] == [("uptime_critical", "true", "verified")]
    assert [c.verified for c in claims] == [True, False]
    assert claims[0].candidate_id == "project:p" and claims[0].extracted_by == "gemini_text"


def test_values_outside_each_fields_form_are_dropped_before_verifying():
    facts, claims = facts_for(
        [
            {"field": "deploy_countries", "value": "United States", "quote": "United States"},
            {"field": "deploy_countries", "value": "us", "quote": "Now shipping"},
            {"field": "uptime_critical", "value": "yes", "quote": "sits idle"},
            {"field": "budget_usd", "value": "5000", "quote": "Stretch"},  # never from a page
            {"field": "need_by_days", "value": "true", "quote": "Stretch"},  # never from a page
            {"field": "made_up", "value": "x", "quote": "Stretch"},
            "not a row",
        ]
    )
    assert [(f.field, f.value) for f in facts] == [("deploy_countries", "US")]
    assert len(claims) == 1


@pytest.mark.parametrize("raw", [None, [], "text", {"facts": None}, {"nope": 1}])
def test_malformed_model_output_yields_nothing(raw):
    if raw == {"facts": None}:
        raw = {"facts": []}
    assert page_facts(raw, "p", URL, PAGE, "run") == ([], [])


def verified(field, value):
    return Fact(field=field, value=value, basis="verified", quote="q", source_url=URL)


def test_merge_keeps_stated_facts_and_labels_them():
    facts, used = merge_facts(ProjectFacts(budget_usd=2500, deploy_countries=["CA"]), [])
    assert facts.budget_usd == 2500
    assert {(u.field, u.value, u.basis) for u in used} == {
        ("budget_usd", "2500.0", "stated"),
        ("deploy_countries", "CA", "stated"),
    }


def test_verified_replaces_stated_and_the_first_verified_value_stands():
    stated = ProjectFacts(uptime_critical=False)
    facts, used = merge_facts(
        stated, [verified("uptime_critical", "true"), verified("uptime_critical", "false")]
    )
    assert facts.uptime_critical is True
    assert [(u.field, u.value, u.basis) for u in used] == [("uptime_critical", "true", "verified")]
    assert stated.uptime_critical is False  # input not mutated


def test_countries_are_a_union_without_duplicates():
    facts, used = merge_facts(
        ProjectFacts(deploy_countries=["US"]),
        [verified("deploy_countries", "US"), verified("deploy_countries", "CA")],
    )
    assert facts.deploy_countries == ["US", "CA"]
    assert [(u.value, u.basis) for u in used] == [("US", "stated"), ("CA", "verified")]


# --- through the API, with fixture projects -------------------------------------------------

COMPANY = {
    "id": "acme",
    "kind": "company",
    "name": "Acme Robotics",
    "robot": "Lifter",
    "use_case": "warehouse case picking",
    "robot_kind": "arm",
    "arm": {
        "joint": "shoulder",
        "payload_kg": 2.0,
        "reach_m": 0.5,
        "links": [{"name": "upper", "mass_kg": 1.0, "com_m": 0.2}],
        "gear_ratio": 50,
        "efficiency": 0.8,
        "omega_max_dps": 90,
        "t_accel_s": 0.5,
        "bus_voltage_v": 24,
        "illustrative": True,
    },
    "deep_line": "shoulder_motor",
    "bom": [{"id": "shoulder_motor", "domain": "actuation", "qty": 1, "part": "NEMA 23 motor"}],
    "intake_sources": [{"url": URL, "reason": "product page"}],
}
CLUB = {
    **COMPANY,
    "id": "club",
    "kind": "club",
    "intake_sources": [],
    "stated": {"deploy_countries": ["CA"], "budget_usd": 2500, "need_by_days": 21},
}


@pytest.fixture
def projects(tmp_path, monkeypatch):
    for p in (COMPANY, CLUB):
        (tmp_path / f"{p['id']}.json").write_text(json.dumps(p))
    monkeypatch.setattr("app.projects.project_dir", lambda: tmp_path)


def fake_intake_http(flash_rows):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.fetch.tinyfish.ai":
            urls = json.loads(request.content)["urls"]
            return httpx.Response(200, json={"results": [{"url": u, "text": PAGE} for u in urls]})
        text = json.dumps({"facts": flash_rows})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run_project_job(client, project_id, mode="replay"):
    from tests.test_jobs_api import NoClaimWorker, sse_events

    client.app.state.runtime.workers = lambda mode: [NoClaimWorker()]
    r = client.post("/api/jobs", json={"mode": mode, "project_id": project_id})
    assert r.status_code == 201, r.text
    return sse_events(client, r.json()["job_id"])


def test_projects_are_listed(client, projects):
    r = client.get("/api/projects")
    assert [p["id"] for p in r.json()] == ["acme", "club"]
    assert set(r.json()[0]) == {"id", "kind", "name", "robot", "use_case"}


@pytest.mark.parametrize("bad", ["nope", "../demo_robot", "ACME"])
def test_unknown_project_is_404(client, projects, bad):
    assert client.post("/api/jobs", json={"project_id": bad}).status_code == 404


def test_club_job_uses_stated_facts_and_skips_intake_and_v3_card(client, projects):
    events = run_project_job(client, "club")
    [project] = [e["data"] for e in events if e["type"] == "project"]
    assert {f["basis"] for f in project["facts"]} == {"stated"}
    assert project["criteria"]["max_lead_time_days"] == 21
    assert project["criteria"]["duty_countries"] == ["CA"]
    assert not [e for e in events if e["type"] in ("compliance", "run_started")]
    assert events[-1]["data"]["stage"] == "DONE"


def test_company_job_verifies_facts_from_its_own_pages(client, projects, monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "recordings_dir", tmp_path / "rec")
    client.app.state.runtime.http = fake_intake_http(
        [
            {
                "field": "deploy_countries",
                "value": "US",
                "quote": "Now shipping in the **United States**",
            },
            {"field": "uptime_critical", "value": "true", "quote": "a robot sits idle"},
            {"field": "sells_to_us_federal", "value": "true", "quote": "Trusted by the US Army."},
        ]
    )
    events = run_project_job(client, "acme", mode="live")
    claims = [
        (e["type"], e["data"]["claim"]["field"]) for e in events if e["type"].startswith("claim")
    ]
    assert claims == [
        ("claim_verified", "deploy_countries"),
        ("claim_verified", "uptime_critical"),
        ("claim_rejected", "sells_to_us_federal"),
    ]
    [project] = [e["data"] for e in events if e["type"] == "project"]
    criteria = project["criteria"]
    assert "supply_risk" in criteria["objectives"] and "us_first" not in criteria["objectives"]
    assert criteria["blocking_lists"] == ["uflpa"]
    assert {(f["field"], f["basis"]) for f in project["facts"]} == {
        ("deploy_countries", "verified"),
        ("uptime_critical", "verified"),
    }


def test_intake_failure_degrades_the_job_and_criteria_still_run(client, projects):
    events = run_project_job(client, "acme")  # replay with nothing recorded
    error = next(e["data"] for e in events if e["type"] == "error")
    assert error["stage"] == "INTAKE" and error["message"].startswith("ReplayMiss")
    assert [e for e in events if e["type"] == "project"]
    assert events[-1]["data"]["stage"] == "DEGRADED"
