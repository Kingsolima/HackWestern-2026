"""Live jobs spend TinyFish credit: on a public deploy they need X-Live-Token."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


class NoClaimWorker:
    name = "swap:none"

    async def run(self, ctx):
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "replay_speed", 0)
    with TestClient(app) as c:
        # never start a real TinyFish run from a test
        c.app.state.runtime.workers = lambda mode: [NoClaimWorker()]
        yield c


def post(client, mode, token=None):
    headers = {"X-Live-Token": token} if token is not None else {}
    return client.post("/api/jobs", json={"mode": mode}, headers=headers)


def test_dev_default_allows_live(client, monkeypatch):
    monkeypatch.setattr(settings, "require_live_token", False)
    assert post(client, "live").status_code == 201


@pytest.mark.parametrize("token", [None, "", "wrong"])
def test_public_deploy_refuses_live_without_the_token(client, monkeypatch, token):
    monkeypatch.setattr(settings, "require_live_token", True)
    monkeypatch.setattr(settings, "live_jobs_token", "s3cret")
    for mode in ("live", "mixed"):
        r = post(client, mode, token)
        assert r.status_code == 403 and "X-Live-Token" in r.json()["detail"]


def test_public_deploy_accepts_the_right_token_and_keeps_replay_open(client, monkeypatch):
    monkeypatch.setattr(settings, "require_live_token", True)
    monkeypatch.setattr(settings, "live_jobs_token", "s3cret")
    assert post(client, "live", "s3cret").status_code == 201
    assert post(client, "replay").status_code == 201


def test_no_token_configured_refuses_every_live_job(client, monkeypatch):
    monkeypatch.setattr(settings, "require_live_token", True)
    monkeypatch.setattr(settings, "live_jobs_token", "")
    assert post(client, "live", "").status_code == 403
    assert post(client, "live", "anything").status_code == 403
