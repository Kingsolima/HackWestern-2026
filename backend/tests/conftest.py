import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def no_discovery(monkeypatch):
    """Jobs in tests run only their workers' seed targets; discovery tests opt back in."""
    monkeypatch.setattr("app.orchestrator.job.plan_queries", lambda: [])
