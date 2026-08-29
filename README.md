# FastAPI Hugging Face RAG

A multi-user Retrieval-Augmented Generation API built with FastAPI, PostgreSQL/pgvector, Redis, and Hugging Face. The project is being implemented in milestones; the foundation currently defines the production-oriented application structure and complete initial data model.

## Foundation status

- Versioned FastAPI application (`/api/v1`)
- Application factory and lifespan cleanup
- PostgreSQL async engine
- Redis async client
- pgvector-enabled Alembic migration
- User, document, chunk, ingestion-job, conversation, and message models
- Ownership foreign keys and cascading deletion
- HNSW cosine vector index
- Health and dependency-readiness endpoints
- Docker Compose for PostgreSQL and Redis
- Docker image, tests, linting, and GitHub Actions CI

Document ingestion, authentication, Hugging Face embeddings, retrieval, generation, citations, and conversations are the next implementation milestones.

## Quick start

```bash
uv sync --dev
cp .env.example .env
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Open Swagger UI at `http://127.0.0.1:8000/docs`.

## System endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Process liveness |
| `GET` | `/api/v1/ready` | PostgreSQL and Redis readiness |

## Structure

```text
app/
├── api/v1/endpoints/  # Versioned HTTP endpoints
├── core/              # Configuration and infrastructure clients
├── models/            # SQLModel database entities
├── schemas/           # Request and response contracts
├── repositories/      # Persistence boundaries
├── services/          # Application and RAG logic
├── workers/           # Background ingestion jobs
└── main.py            # Application factory
alembic/versions/      # Database migrations
tests/unit/            # Isolated behavior tests
tests/integration/     # API and infrastructure tests
```

## Configuration

Copy `.env.example` and set a secure `JWT_SECRET` and `HF_TOKEN`. The embedding dimension must match `HF_EMBEDDING_MODEL`; changing it requires a database migration because pgvector dimensions are part of the column type.

## Validation

```bash
uv run ruff check .
uv run pytest -q
uv run alembic upgrade head --sql
```

Live Hugging Face calls will be isolated behind async service interfaces and mocked in CI so tests remain deterministic and do not incur inference charges.
