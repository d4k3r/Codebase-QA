"""Application configuration loaded from environment variables and .env."""

from functools import lru_cache

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Small set of settings needed by the application."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://codebase_qa:codebase_qa@localhost:5432/codebase_qa",
        validation_alias="DATABASE_URL",
    )
    app_name: str = Field(default="Codebase QA V2", validation_alias="APP_NAME")
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        validation_alias="EMBEDDING_MODEL_NAME",
    )
    default_top_k: int = Field(default=5, ge=1, validation_alias="DEFAULT_TOP_K")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_model_name: str | None = Field(default=None, validation_alias="LLM_MODEL_NAME")


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the application process."""

    return Settings()
