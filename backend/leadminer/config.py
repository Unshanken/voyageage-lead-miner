from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VoyageAge Lead Miner"
    environment: str = "development"
    database_url: str = "sqlite:///./leadminer.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    llm_base_url: str | None = None
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_model: str | None = None

    hunter_api_key: str | None = Field(default=None, repr=False)
    apollo_api_key: str | None = Field(default=None, repr=False)
    prospeo_api_key: str | None = Field(default=None, repr=False)
    email_verifier_api_key: str | None = Field(default=None, repr=False)

    crawler_max_pages_per_domain: int = Field(default=12, ge=1, le=50)
    crawler_max_depth: int = Field(default=2, ge=0, le=4)
    crawler_request_timeout: float = Field(default=15, ge=1, le=60)
    crawler_max_response_bytes: int = Field(default=2_000_000, ge=100_000)
    crawler_max_retries: int = Field(default=2, ge=0, le=5)
    crawler_global_concurrency: int = Field(default=8, ge=1, le=50)
    crawler_domain_concurrency: int = Field(default=2, ge=1, le=8)
    crawler_user_agent: str = "VoyageAgeLeadMiner/0.1 (+https://www.voyageage.com/)"
    crawler_delay_seconds: float = Field(default=0.5, ge=0)
    crawler_max_redirects: int = Field(default=5, ge=0, le=10)
    crawler_text_max_chars: int = Field(default=12_000, ge=1_000, le=100_000)
    crawler_freshness_hours: int = Field(default=24, ge=1, le=720)
    crawler_retry_after_max_seconds: float = Field(default=10, ge=0, le=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()
