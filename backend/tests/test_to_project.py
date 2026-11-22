import csv
import io
import json
from pathlib import Path

import httpx
import pytest

from app.config import REPO_ROOT, Settings, settings
from app.engineering.compliance import compliance_card
from app.engineering.concerns import CONCERNS_SCHEMA, concerns_prompt, confirm_concerns
from app.engineering.criteria import derive_criteria
from app.intake.extract import confirm, prompt, response_schema
from app.intake.schema import WHEELED, Answers, CompanyFact
from app.intake.to_project import project_from_onboarding
from app.orchestrator.workers import FakeSwapWorker
from app.projects import list_projects, load_project
from app.schemas import BomRow, Robot
from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder


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


# --- The AR4 parts list (docs/demo-company-bom.csv, read from Annin Robotics' BOM PDF) ---


def ar4_rows() -> list[BomRow]:
    """The file as the onboarding page sends it (frontend/src/onboarding/bomCsv.ts)."""
    text = (REPO_ROOT / "docs" / "demo-company-bom.csv").read_text()
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        cost = r.pop("unit_cost_usd")
        rows.append(
            BomRow(
                **{k: v for k, v in r.items() if v != ""},
                unit_cost_usd=None if cost in ("", "unknown") else cost,
            )
        )
    return rows


def ar4_project():
    robot = demo_robot().model_copy(update={"bom": ar4_rows()})
    return project_from_onboarding(COMPANY, robot, list_projects())


def test_ar4_parts_list_states_no_price_or_origin_and_every_row_names_its_page():
    rows = ar4_rows()
    assert 40 <= len(rows) <= 60
    assert all(r.unit_cost_usd is None and r.origin == "unknown" for r in rows)
    assert all(r.source_page for r in rows)
    assert {r.category for r in rows} == {
        "actuation",
        "transmission",
        "structure",
        "electronics",
        "power",
        "sensors",
    }


def test_ar4_parts_list_runs_as_the_researched_arm_with_j2_as_the_deep_line():
    project = ar4_project()
    reference = load_project("ar4_club")
    assert (project.robot_kind, project.cad_robot) == ("arm", "ar4")
    assert project.arm == reference.arm and project.wheeled is None
    deep = next(line for line in project.bom if line.id == project.deep_line)
    assert deep.part == "J2 gear head motor"
    assert deep.part_number == "23HS22-2804D-YGS50-AR4" and deep.manufacturer == "Stepperonline"
    # Price and origin are not in the PDF: they come from the research, and the note says so.
    assert (deep.unit_price_usd, deep.origin_country, deep.origin_tier) == (152.52, "CN", "T3")
    assert deep.sources and "not from your parts list" in deep.notes
    others = [line for line in project.bom if line.id != project.deep_line]
    assert all(line.unit_price_usd is None and line.origin_country is None for line in others)


def test_ar4_subsystems_set_the_domain_so_a_motor_mount_is_not_a_motor():
    by_part = {line.part: line for line in ar4_project().bom}
    assert by_part["J1 & J3 motor mounts"].domain == "structure"
    assert by_part["Nema 11 bracket for the J4 motor"].component_class is None
    assert by_part["HTD 550-5M belt"].domain == "actuation"
    assert by_part["DM332T digital stepper driver"].component_class == "power_electronics"
    assert by_part["3144 Hall effect sensor 3.3v"].domain == "sensing"
    assert by_part["Teensy 4.1 microcontroller board (with pins)"].domain == "compute"
    motors = [line.part for line in by_part.values() if line.component_class == "motor"]
    assert len(motors) == 6 and all("motor" in m for m in motors)
    assert "page 33" in by_part["J1 gear head motor"].notes


def test_a_parts_list_without_a_known_arm_motor_stays_wheeled():
    project = project_from_onboarding(COMPANY, demo_robot(), list_projects())
    assert project.robot_kind == "wheeled" and project.arm is None


def test_compliance_card_leaves_unpriced_parts_out_and_says_so():
    robot = demo_robot()
    unpriced = robot.bom[0].model_copy(update={"unit_cost_usd": None})
    card = compliance_card(robot.model_copy(update={"bom": [unpriced, *robot.bom[1:]]}))
    assert any("have no price" in note for note in card.notes)


def test_onboarded_ar4_job_scores_every_part_and_builds_the_ar4(client):
    from tests.test_jobs_api import sse_events

    robot = demo_robot().model_copy(update={"bom": ar4_rows()}).model_dump(mode="json")
    client.app.state.runtime.workers = lambda mode: [FakeSwapWorker()]
    body = {"mode": "replay", "robot": robot, "company": [c.model_dump() for c in COMPANY]}
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 201, r.text
    events = sse_events(client, r.json()["job_id"])
    assert events[-1]["data"]["stage"] == "DONE"
    project = next(e for e in events if e["type"] == "project")["data"]["project"]
    assert project["robot_kind"] == "arm" and project["robot_params"]["joint"] == "J2 shoulder"
    assert project["cad_robot"] == "ar4"
    recs = [e["data"]["recommendation"] for e in events if e["type"] == "recommendation"]
    assert len(recs) == len(robot["bom"])
    # No origin on the other parts and a federal buyer: unknown is investigated, never kept.
    unknown = [rec for rec in recs if rec["line_id"] != project["deep_line"]]
    assert {rec["action"] for rec in unknown} == {"investigate"}
    assert [e for e in events if e["type"] == "alternative"]


@pytest.mark.anyio
async def test_the_demo_company_in_docs_replays_offline():
    """docs/DEMO-COMPANY.md must need no Gemini call: the reading of its answers and of what it
    wants to avoid are recorded. Changing an answer or a part name in the CSV needs a new
    recording (one mixed run), and this test says so."""
    answers = Answers.model_validate_json(
        (Path(__file__).parent / "fixtures" / "ar4_company_answers.json").read_text()
    )
    recorder = Recorder(settings.recordings_dir, "replay", replay_speed=0)
    model = Settings.model_fields["gemini_flash_model"].default
    async with httpx.AsyncClient() as http:
        gemini = GeminiClient(recorder, http, "", model)
        raw = await gemini.extract_json(prompt(answers, WHEELED), response_schema(WHEELED))
        company, stated, dropped = confirm(raw, answers, WHEELED)
        assert (stated, dropped) == ([], [])  # no drivetrain answer: the job stays in replay
        robot = demo_robot().model_copy(update={"bom": ar4_rows()})
        project = project_from_onboarding(company, robot, list_projects())
        assert project.name == "Northfield Robotics" and project.robot_kind == "arm"
        assert project.stated.sells_to_us_federal is True and project.stated.need_by_days == 30
        raw = await gemini.extract_json(
            concerns_prompt(project.avoid, project.bom), CONCERNS_SCHEMA
        )
    concerns, deps = confirm_concerns(raw, project.avoid, project.bom)
    assert {c.kind for c in concerns} == {"material", "supplier"}
    assert project.deep_line in {d.line_id for d in deps if d.depends == "likely"}
