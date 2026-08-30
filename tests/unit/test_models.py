from sqlmodel import SQLModel

from app.models import (  # noqa: F401
    AnswerFeedback,
    ApiKey,
    Conversation,
    Document,
    DocumentChunk,
    IngestionJob,
    Message,
    User,
)


def test_expected_tables_are_registered() -> None:
    assert set(SQLModel.metadata.tables) == {
        "users",
        "documents",
        "document_chunks",
        "ingestion_jobs",
        "conversations",
        "messages",
        "answer_feedback",
        "api_keys",
    }


def test_vector_dimension_matches_configuration() -> None:
    vector_type = SQLModel.metadata.tables["document_chunks"].c.embedding.type
    assert vector_type.dim == 1024
