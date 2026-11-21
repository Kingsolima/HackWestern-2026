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

    tinyfish_api_key: str = ""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/redesign"

    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    auth0_domain: str = ""
    auth0_audience: str = ""

    data_dir: Path = REPO_ROOT / "data"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
