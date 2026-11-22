import json

from app.config import settings
from app.engineering.criteria import derive_criteria
from app.intake.schema import CompanyFact
from app.intake.to_project import project_from_onboarding
from app.orchestrator.workers import FakeSwapWorker
from app.schemas import Robot


def demo_robot() -> Robot:
    return Robot.model_validate_json((settings.data_dir / "demo_robot.json").read_text())


def fact(field: str, value: str) -> CompanyFact:
    return CompanyFact(field=field, label=field, value=value, quote="")


COMPANY = [
    fact("company_name", "Example Robotics"),
    fact("kind", "company"),
    fact("use_case", "carries parts bins"),
    fact("sells_to_us_federal", "yes"),
    fact("deploy_countries", "US, CA"),
    fact("uptime_critical", "yes"),
    fact("budget_usd", "$1,600"),
    fact("need_by_days", "30 days"),
]


def test_bom_rows_become_lines_with_a_domain_and_the_motor_is_the_deep_line():
    project = project_from_onboarding(COMPANY, demo_robot())
    domains = {line.part: line.domain for line in project.bom}
    assert domains["Drive motor (NEMA 23)"] == "actuation"
    assert domains["Motor driver"] == "power"  # not a motor
    assert domains["Wheel encoder"] == "sensing"  # not structure
    assert domains["24V battery pack"] == "power"
    assert domains["Single-board computer"] == "compute"
    assert domains["Aluminum base plate"] == "structure"
    assert domains["Wiring harness"] == "other"
    deep = next(line for line in project.bom if line.id == project.deep_line)
    assert deep.part == "Drive motor (NEMA 23)" and project.deep_frame == "23"
    assert (deep.unit_price_usd, deep.origin_country, deep.qty) == (45.0, "CN", 2)
    battery = next(line for line in project.bom if line.part == "24V battery pack")
    assert battery.origin_country is None  # "unknown" is not a country
    assert project.wheeled == demo_robot().requirements and project.cad_robot == "wheeled"
    assert (project.name, project.kind, project.use_case) == (
        "Example Robotics",
        "company",
        "carries parts bins",
    )


def test_stated_facts_come_from_the_company_answers_and_fire_the_criteria_rules():
    project = project_from_onboarding(COMPANY, demo_robot())
    stated = project.stated
    assert stated.sells_to_us_federal is True and stated.uptime_critical is True
    assert stated.deploy_countries == ["US", "CA"]
    assert (stated.budget_usd, stated.need_by_days) == (1600.0, 30)
    fired = {r.rule_id for r in derive_criteria(stated).reasons}
    assert {"C1", "C2", "C3"} <= fired
    nothing = project_from_onboarding([], demo_robot()).stated
    assert nothing.sells_to_us_federal is None and nothing.deploy_countries == []


def test_frame_is_read_from_the_motor_row_and_a_bom_without_a_motor_still_gets_one():
    robot = demo_robot()
    rows = [r.model_copy(update={"part": "NEMA 34 stepper"}) for r in robot.bom[:1]]
    assert project_from_onboarding([], robot.model_copy(update={"bom": rows})).deep_frame == "34"
    no_motor = robot.model_copy(update={"bom": robot.bom[2:4]})
    project = project_from_onboarding([], no_motor)
    deep = next(line for line in project.bom if line.id == project.deep_line)
    assert deep.part == "Drive motor (not in your parts list)" and deep.qty == 2
    assert deep.unit_price_usd is None and len(project.bom) == 3


def test_onboarded_job_gets_a_project_a_risk_row_per_part_and_recommendations(client):
    from tests.test_jobs_api import sse_events

    robot = json.loads((settings.data_dir / "demo_robot.json").read_text())
    client.app.state.runtime.workers = lambda mode: [FakeSwapWorker()]
    body = {"mode": "replay", "robot": robot, "company": [c.model_dump() for c in COMPANY]}
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 201, r.text
    events = sse_events(client, r.json()["job_id"])
    assert events[-1]["data"]["stage"] == "DONE"  # nothing to read in INTAKE is not a failure
    project = next(e for e in events if e["type"] == "project")["data"]
    assert project["project"]["name"] == "Example Robotics"
    risk_lines = {e["data"]["line"]["id"] for e in events if e["type"] == "risk_line"}
    assert len(risk_lines) == len(robot["bom"])
    recs = [e["data"]["recommendation"] for e in events if e["type"] == "recommendation"]
    assert {rec["line_id"] for rec in recs} == risk_lines
    assert [e for e in events if e["type"] == "alternative"]
    assert [e for e in events if e["type"] == "check_result"]
