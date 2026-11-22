"""The motor-side requirement for a job: the deep line's formula picked by robot kind."""

from app.engineering.arm import arm_requirement
from app.engineering.spec_checks import Requirement, requirement
from app.schemas import Project, Robot


def requirement_for(robot: Robot, project: Project | None) -> Requirement:
    if project is None:
        return requirement(robot.requirements)
    if project.robot_kind == "arm":
        if project.arm is None:
            raise ValueError(f"project {project.id} is an arm without arm parameters")
        return arm_requirement(project.arm)
    if project.wheeled is None:
        raise ValueError(f"project {project.id} is wheeled without wheel parameters")
    return requirement(project.wheeled)
