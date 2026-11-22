import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeCadClient:
    """Stands in for the CAD worker so API tests never call a real one on CAD_WORKER_URL."""

    def __init__(self, base_url: str, http) -> None:
        self.base_url = base_url

    async def build(self, design_id: str, **params):
        return {
            "design_id": design_id,
            "glb_url": f"/designs/{design_id}/glb",
            "step_url": f"/designs/{design_id}/step",
            "fit": {"params": params},
        }


@pytest.fixture(autouse=True)
def no_real_cad_worker(monkeypatch):
    monkeypatch.setattr("app.orchestrator.runtime.CadClient", FakeCadClient)
