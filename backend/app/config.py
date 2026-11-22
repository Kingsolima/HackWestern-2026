"""Settings loaded from the environment / repo-root .env. See .env.example for the names."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        extra="ignore",
    )

    cors_origins: str = "http://localhost:5173"
    cad_worker_url: str = "http://localhost:8001"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"

    tinyfish_api_key: str = ""
    # Live jobs spend TinyFish credit. On a public deploy set REQUIRE_LIVE_TOKEN=true and
    # LIVE_JOBS_TOKEN; then a live/mixed job needs header X-Live-Token. With no token set,
    # every live job is refused. Replay jobs are always open.
    require_live_token: bool = False
    live_jobs_token: str = ""

    tiger_enabled: bool = False  # board + agent_runs on Tiger Data at DATABASE_URL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/redesign"

    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    auth0_domain: str = ""
    auth0_audience: str = ""

    data_dir: Path = REPO_ROOT / "data"
    recordings_dir: Path = REPO_ROOT / "data" / "recordings"
    replay_speed: float = 1.0

    agent_slots: int = 2
    browser_slots: int = 5
    search_slots: int = 4
    fetch_slots: int = 4
    gemini_slots: int = 4
    max_agent_runs_per_job: int = 8

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
