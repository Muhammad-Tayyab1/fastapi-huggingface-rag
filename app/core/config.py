from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FastAPI Hugging Face RAG"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/ragdb"
    redis_url: str = "redis://localhost:6379/0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    sentry_dsn: SecretStr = SecretStr("")
    sentry_traces_sample_rate: float = Field(default=0, ge=0, le=1)

    jwt_secret: SecretStr = SecretStr("change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_min: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    hf_token: SecretStr = SecretStr("")
    hf_provider: str = "auto"
    hf_embedding_model: str = "thenlper/gte-large"
    hf_chat_model: str = "Qwen/Qwen2.5-7B-Instruct-1M"
    hf_timeout_seconds: float = Field(default=60, gt=0)
    hf_embedding_batch_size: int = Field(default=16, ge=1, le=128)
    hf_max_retries: int = Field(default=3, ge=1, le=10)

    embedding_dimension: int = Field(default=1024, gt=0)
    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=120, ge=0)
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    retrieval_min_score: float = Field(default=0.65, ge=0, le=1)
    rag_max_context_chars: int = Field(default=12000, ge=1000, le=100000)
    rag_max_output_tokens: int = Field(default=700, ge=1, le=4096)
    rag_temperature: float = Field(default=0.1, ge=0, le=2)
    register_rate_limit_per_hour: int = Field(default=5, ge=1)
    login_rate_limit_per_15_min: int = Field(default=10, ge=1)
    rag_rate_limit_per_min: int = Field(default=30, ge=1)
    upload_rate_limit_per_hour: int = Field(default=20, ge=1)
    max_upload_mb: int = Field(default=20, ge=1, le=200)

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: Path = Path("storage")
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str = ""
    s3_access_key_id: SecretStr = SecretStr("")
    s3_secret_access_key: SecretStr = SecretStr("")
    s3_prefix: str = "documents"
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.app_env == "production" and self.jwt_secret.get_secret_value() == "change-me":
            raise ValueError("JWT_SECRET must be configured in production")
        if self.app_env == "production" and not self.hf_token.get_secret_value():
            raise ValueError("HF_TOKEN must be configured in production")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET must be configured when STORAGE_BACKEND=s3")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
