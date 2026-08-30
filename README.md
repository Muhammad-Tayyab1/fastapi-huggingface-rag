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
- JWT registration, login, refresh, and profile endpoints
- Repository and service boundaries for user authentication
- Authenticated PDF, DOCX, and TXT uploads with content validation
- User-owned document listing, status, deletion, and reprocessing jobs
- ARQ/Redis background ingestion with idempotent chunk replacement
- PDF, DOCX, and TXT extraction, normalization, and deterministic chunking
- Batched Hugging Face embeddings with retries and strict dimension validation
- Unit-normalized pgvector values and `ready` document promotion
- Ownership-filtered pgvector cosine retrieval
- Grounded Hugging Face answers with page-level source citations
- User-owned conversation history with persisted questions, answers, and citations
- True token streaming through Server-Sent Events
- Redis-backed distributed rate limiting with hashed identity keys
- Request IDs, structured JSON access logs, and optional Sentry monitoring
- Non-root production container with health checks and graceful init

The main implementation milestones are complete; live infrastructure and Hugging Face validation remain environment-specific deployment tasks.

## Quick start

```bash
uv sync --dev
cp .env.example .env
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# In another terminal:
uv run arq app.workers.settings.WorkerSettings
```

Open Swagger UI at `http://127.0.0.1:8000/docs`.

## System endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Process liveness |
| `GET` | `/api/v1/ready` | PostgreSQL and Redis readiness |

## Authentication endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Create a user account |
| `POST` | `/api/v1/auth/login` | Issue access and refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate the token pair |
| `GET` | `/api/v1/users/me` | Read the current profile |
| `PATCH` | `/api/v1/users/me` | Update the current profile |

## Document endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/documents/` | Upload a PDF, DOCX, or UTF-8 text document |
| `GET` | `/api/v1/documents/` | List the current user's documents |
| `GET` | `/api/v1/documents/{id}` | Read owned document metadata |
| `GET` | `/api/v1/documents/{id}/status` | Read document and ingestion status |
| `POST` | `/api/v1/documents/{id}/reprocess` | Queue failed/completed processing again |
| `DELETE` | `/api/v1/documents/{id}` | Delete the document and stored file |

## RAG endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/rag/search` | Return relevant owned document chunks and similarity scores |
| `POST` | `/api/v1/rag/query` | Generate a grounded answer with document/page citations |
| `POST` | `/api/v1/rag/query/stream` | Stream sources, answer tokens, and completion metadata over SSE |

Retrieval always filters both chunks and joined documents by the authenticated user's ID, optionally narrows the search to selected document IDs, excludes unembedded chunks, and only searches documents in the `ready` state. When no result meets the configured similarity threshold, the API returns a deterministic no-context response without calling the language model.

## Conversation endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/conversations/` | Create a conversation |
| `GET` | `/api/v1/conversations/` | List owned conversations |
| `GET` | `/api/v1/conversations/{id}` | Read a conversation with messages |
| `GET` | `/api/v1/conversations/{id}/messages` | List persisted messages and citations |
| `DELETE` | `/api/v1/conversations/{id}` | Delete an owned conversation |

Both regular and streaming RAG queries accept an optional `conversation_id`. If omitted, the API creates a conversation automatically. Recent user/assistant messages are added to the generation prompt, and completed exchanges are persisted atomically. Streaming emits `sources`, repeated `token`, and final `done` SSE events.

Uploads create an ingestion job and enqueue it in Redis. The worker extracts and normalizes text, replaces existing chunks idempotently, records page/chunk metadata, requests embeddings from Hugging Face in configurable batches, and promotes the document from `extracted` to `ready`. Provider timeouts are retried with exponential backoff, and unexpected embedding dimensions fail the job safely.

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

## Production operations

Sensitive authentication, upload, and RAG endpoints use Redis-backed rate limits shared by all API workers. Identity components are SHA-256 hashed before becoming Redis keys. If Redis is unavailable, protected operations fail closed with `503` rather than silently disabling abuse protection.

Every response includes `X-Request-ID`. Valid caller-supplied IDs are propagated; invalid values are replaced. Access logs are JSON and include method, path, status, duration, and request ID. Set `SENTRY_DSN` to enable error monitoring without sending default personally identifiable information.

The Docker image runs as a non-root user and includes an API health check. Run migrations as a release/pre-deploy command before starting new API and worker instances:

```bash
uv run alembic upgrade head
```
