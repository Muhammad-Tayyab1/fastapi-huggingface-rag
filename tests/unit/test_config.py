import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError):
        Settings(chunk_size=200, chunk_overlap=200)


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret="change-me")


def test_s3_storage_requires_bucket() -> None:
    with pytest.raises(ValidationError, match="S3_BUCKET"):
        Settings(storage_backend="s3", s3_bucket="")


def test_render_postgres_url_uses_asyncpg_driver() -> None:
    configured = Settings(database_url="postgresql://user:secret@database/rag")

    assert configured.database_url == "postgresql+asyncpg://user:secret@database/rag"


def test_production_metrics_require_scrape_token() -> None:
    with pytest.raises(ValidationError, match="METRICS_BEARER_TOKEN"):
        Settings(
            app_env="production",
            jwt_secret="secure",
            hf_token="hf_test",
            metrics_enabled=True,
            metrics_bearer_token="",
        )
