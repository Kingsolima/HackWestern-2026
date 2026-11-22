import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def no_discovery(monkeypatch):
    """Jobs in tests run only their workers' seed targets; discovery tests opt back in."""
    monkeypatch.setattr("app.orchestrator.job.plan_queries", lambda project=None: [])


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "replay_speed", 0)
    # Never reach a real CAD worker on the dev machine; tests that need one install fake_cad.
    monkeypatch.setattr(settings, "cad_worker_url", "http://cad.invalid")
    with TestClient(app) as c:
        yield c
