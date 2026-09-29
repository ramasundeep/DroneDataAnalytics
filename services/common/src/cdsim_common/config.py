"""Service configuration from environment variables (prefix ``CDSIM_``).

All services read the same settings class; each only uses what it needs.
Defaults match ``.env.example`` and docker-compose.yml so that a service run
directly on a laptop (outside Docker) finds the dev stack on localhost.
Secrets come from the environment (``.env`` locally, generated per box in the
field) and are never committed. See CLAUDE.md §"Secrets".
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from cdsim_common.paths import repo_root


def _default_dir(*parts: str) -> Path:
    root = repo_root()
    return root.joinpath(*parts) if root else Path("/opt/cdsim").joinpath(*parts)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CDSIM_", extra="ignore")

    service_name: str = "cdsim"
    log_level: str = "INFO"

    # PostgreSQL + TimescaleDB
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "cdsim"
    db_password: SecretStr = SecretStr("cdsim-dev-only")
    db_name: str = "cdsim"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO (S3 API)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "cdsim"
    minio_secret_key: SecretStr = SecretStr("cdsim-dev-only")
    minio_secure: bool = False
    recordings_bucket: str = "cdsim-recordings"
    areas_bucket: str = "cdsim-areas"

    # Data directories (mounted read-only into containers)
    schemas_dir: Path = Field(default_factory=lambda: _default_dir("schemas", "json"))
    platforms_dir: Path = Field(default_factory=lambda: _default_dir("platforms"))
    areas_dir: Path = Field(default_factory=lambda: _default_dir("terrain", "areas"))
    scenarios_dir: Path = Field(default_factory=lambda: _default_dir("scenarios"))
    rubrics_dir: Path = Field(
        default_factory=lambda: _default_dir("services", "assessment", "rubrics")
    )

    # Comma-separated name=url pairs the API polls for the aggregate health view.
    service_urls: str = ""

    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password.get_secret_value()}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def service_url_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for item in filter(None, (s.strip() for s in self.service_urls.split(","))):
            name, _, url = item.partition("=")
            if not url:
                raise ValueError(f"CDSIM_SERVICE_URLS entry '{item}' must be name=url")
            out[name.strip()] = url.strip().rstrip("/")
        return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
