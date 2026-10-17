from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.fastapi",
        env_file_encoding="utf-8",
        env_prefix="FASTAPI_",
        extra="ignore",
    )

    app_name: str = "SmartRoll"
    environment: str = "local"
    database_url: str = (
        "postgresql+psycopg://smartroll_fastapi:smartroll_fastapi@"
        "fastapi_db:5432/smartroll_fastapi"
    )
    redis_url: str = "redis://fastapi_redis:6379/0"
    storage_root: Path = Path("/var/lib/smartroll")
    allowed_origins: list[str] = [
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    ]
    allowed_hosts: list[str] = ["127.0.0.1", "localhost", "testserver"]
    csrf_secret: SecretStr = SecretStr("replace-this-for-local-development")
    enrollment_max_bytes: int = 10 * 1024 * 1024
    classroom_max_bytes: int = 20 * 1024 * 1024
    completed_job_retention_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
