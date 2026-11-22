"""Risk data (sourced files) and the RISK_BASELINE / ALTERNATIVES / RECOMMEND stages, run on the
real demo projects in data/projects."""

import pytest

from app.engineering.risk_data import bottleneck, duty_pct, list_hits
from app.schemas import Criteria, Objective

US = Criteria(objectives=[Objective.performance], duty_countries=["US"], blocking_lists=["uflpa"])
CA = Criteria(objectives=[Objective.performance], duty_countries=["CA"])
ALL_LISTS = Criteria(
    objectives=[Objective.performance], blocking_lists=["uflpa", "dod_1260h", "fcc_covered"]
)


def test_article_levels_with_page_sources():
    assert bottleneck("motor")[:2] == ("low", f"{bottleneck('motor')[1]}")
    assert bottleneck("motor")[0] == "low" and bottleneck("motor")[1].endswith("#page=6")
    assert bottleneck("harmonic_drive")[0] == "high"
    assert bottleneck("encoder")[0] == "medium"
    assert bottleneck("gearbox_planetary") == ("unknown", None, "")
    assert bottleneck(None)[0] == "unknown"


def test_us_duty_stacks_from_the_researched_layers():
    pct, note = duty_pct("8501.31.40", "CN", US)
    assert pct == pytest.approx(41.5) and "25%" in note  # 4% MFN + 25% List 2 + 12.5%
    assert duty_pct("8501.31.40", "US", US)[0] == 0
    assert duty_pct("8501.31.40", "GB", US)[0] == pytest.approx(14)


@pytest.mark.parametrize(
    ("hts", "origin", "criteria", "why"),
    [
        ("9999.99.99", "CN", CA, "CA duty for HS 9999.99.99 not researched"),
        ("8501.31.40", None, US, "origin unknown"),
        ("9999.99.99", "CN", US, "not researched"),
        ("8501.31.40", "TW", US, "no plain rate"),  # "301 forced labor: 10 - 4" is a rule
        ("8501.31.40", "CN", Criteria(objectives=[]), "no import market"),
    ],
)
def test_duty_is_unknown_rather_than_guessed(hts, origin, criteria, why):
    pct, note = duty_pct(hts, origin, criteria)
    assert pct is None and why in note


def test_canadian_duty_is_free_on_motors_and_hst_is_not_counted():
    pct, note = duty_pct("8501.31.40", "CN", CA)
    assert pct == 0 and "MFN Free" in note and "no surtax" in note
    assert duty_pct("8504.40.40", "US", CA)[0] == 0
    assert duty_pct("8501.31.40", "CA", CA) == (0.0, "made in CA: no import duty")


def test_canadian_china_surtax_hits_aluminum_chapters(monkeypatch):
    from app.engineering import risk_data

    data = risk_data._yaml("research/canada_duty.yaml")
    patched = {**data, "hs6": {**data["hs6"], "7616.99": {"mfn_pct": 6.5}}}
    monkeypatch.setattr(risk_data, "_yaml", lambda rel: patched if "canada" in rel else data)
    pct, note = duty_pct("7616.99.10", "CN", CA)
    assert pct == 31.5 and "CN surtax 25%" in note
    assert duty_pct("7616.99.10", "JP", CA)[0] == 6.5


def test_list_screen_matches_whole_names_only_on_the_criteria_lists():
    assert list_hits("Huawei Technologies Company", ALL_LISTS) == ["fcc_covered"]
    assert list_hits("Huawei Technologies Company", US) == []
    assert list_hits("STEPPERONLINE", ALL_LISTS) == []
    assert list_hits("Teknic", ALL_LISTS) == []
    assert list_hits(None, ALL_LISTS) == [] and list_hits("Co", ALL_LISTS) == []


def run_project(client, project_id):
    from app.orchestrator.workers import FakeSwapWorker
    from tests.test_jobs_api import sse_events

    client.app.state.runtime.workers = lambda mode: [FakeSwapWorker()]
    r = client.post("/api/jobs", json={"mode": "replay", "project_id": project_id})
    assert r.status_code == 201, r.text
    return sse_events(client, r.json()["job_id"])


def test_club_job_ends_with_ranked_recommendations(client):
    events = run_project(client, "ar4_club")
    risks = [e["data"] for e in events if e["type"] == "risk_line"]
    assert [r["line"]["id"] for r in risks] == [
        "j2_motor",
        "motor_package_rest",
        "combo_kit",
        "j2_motor",
    ]
    baseline, final = risks[0]["risk"], risks[-1]["risk"]
    assert "sources" not in {f["name"] for f in baseline["factors"]}
    sources = next(f for f in final["factors"] if f["name"] == "sources")
    # the fake job's Teknic 2310S makes 0.32 N-m; the AR4 J2 needs 0.77 N-m, so it is rejected
    assert sources["value"] == "0 eligible alternatives" and sources["level"] == "high"
    trade = next(f for f in final["factors"] if f["name"] == "trade")
    assert trade["level"] == "low" and "MFN Free" in trade["reason"]
    [alt] = [e["data"]["alternative"] for e in events if e["type"] == "alternative"]
    assert alt["line_id"] == "j2_motor" and alt["origin_country"] == "US"
    assert alt["verdict"] == "rejected"
    recs = [e["data"] for e in events if e["type"] == "recommendation"]
    assert [r["rank"] for r in recs] == [1, 2, 3]
    j2 = next(r["recommendation"] for r in recs if r["recommendation"]["line_id"] == "j2_motor")
    assert j2["action"] == "keep" and j2["reason"] == "No eligible alternative lowers the risk."
    assert {r["recommendation"]["line_id"] for r in recs} == {
        "j2_motor",
        "motor_package_rest",
        "combo_kit",
    }
    stages = [e["data"]["stage"] for e in events if e["type"] == "stage"]
    assert stages.index("RISK_BASELINE") < stages.index("ALTERNATIVES") < stages.index("RECOMMEND")
    assert not [e for e in events if e["type"] == "compliance"]
    assert events[-1]["data"]["stage"] == "DONE"


def test_stretch_job_without_recorded_intake_still_maps_risk(client, monkeypatch):
    from app.api import jobs
    from app.projects import load_project
    from app.schemas import IntakeSource

    stretch = load_project("stretch").model_copy(
        update={"intake_sources": [IntakeSource(url="https://never.recorded/x", reason="test")]}
    )
    monkeypatch.setattr(jobs, "load_project", lambda pid: stretch)
    events = run_project(client, "stretch")
    assert events[-1]["data"]["stage"] == "DEGRADED"  # intake not recorded in this test
    lines = {e["data"]["line"]["id"]: e["data"] for e in events if e["type"] == "risk_line"}
    assert lines["shoulder_gearbox"]["risk"]["overall"] == "high"  # harmonic drive
    assert lines["battery"]["risk"]["blocked"] is True  # sold out
    assert all(e["data"]["line"]["illustrative"] for e in events if e["type"] == "risk_line")
    recs = [e["data"]["recommendation"] for e in events if e["type"] == "recommendation"]
    assert recs[-1]["action"] == "keep"
