"""Demo projects (docs/BUILD-PLAN-v4.md section 2): data/projects/<id>.json."""

import re

from app.config import Settings
from app.schemas import Project

_ID = re.compile(r"^[a-z0-9_-]{1,40}$")


class UnknownProject(LookupError):
    pass


def project_dir():
    return Settings().data_dir / "projects"


def load_project(project_id: str) -> Project:
    path = project_dir() / f"{project_id}.json"
    if not _ID.match(project_id) or not path.is_file():
        raise UnknownProject(project_id)
    return Project.model_validate_json(path.read_text())


def list_projects() -> list[Project]:
    return [
        Project.model_validate_json(p.read_text()) for p in sorted(project_dir().glob("*.json"))
    ]
