# Render deployment

The repository includes a Render Blueprint for an API service, an ARQ background worker, managed PostgreSQL, and managed Key Value (Redis-compatible) storage. PostgreSQL and Key Value traffic stays on Render's private network. Uploaded source files use S3-compatible object storage, so both application services remain stateless.

## Prerequisites

- A Render account connected to this GitHub repository
- A Hugging Face access token with permission to call the configured inference models
- An AWS S3 bucket or S3-compatible bucket and credentials
- Paid service plans suitable for an always-on API and worker

## First deployment

1. In Render, create a new Blueprint and select this repository. Render discovers `render.yaml`.
2. Select the same region for every resource. Review the proposed plans before applying the Blueprint.
3. Enter `HF_TOKEN`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` when prompted.
4. For a non-AWS provider, set `S3_ENDPOINT_URL` on both the API and worker. Update `S3_REGION` if required by the provider.
5. Apply the Blueprint. The API pre-deploy command runs all Alembic migrations, including `CREATE EXTENSION vector`.
6. Confirm `/api/v1/health` returns `200`, then confirm `/api/v1/ready` reports PostgreSQL and Redis as ready.
7. Set `CORS_ORIGINS` to a JSON array containing only the deployed frontend origins, if browser clients call the API.

Render supplies PostgreSQL URLs as `postgresql://...`; application settings safely normalize these to SQLAlchemy's asyncpg driver URL. Do not manually place credentials in `render.yaml` or commit a populated `.env` file.

## Deployment order and migrations

The web service owns schema migrations through `preDeployCommand`. For the initial launch, wait for the API deployment and migration to succeed before manually redeploying the worker if it started earlier. For later releases, deploy the API first when a migration is not backward compatible, then deploy the worker.

Alembic migrations must remain backward compatible with the currently running API and worker during rolling deployments. Use additive migrations first; remove old columns or behavior in a later release.

## Verification

After every deployment:

```bash
curl --fail https://YOUR-SERVICE.onrender.com/api/v1/health
curl --fail https://YOUR-SERVICE.onrender.com/api/v1/ready
```

Register a test user, upload a small UTF-8 text file, wait for its ingestion status to become `ready`, and run one RAG query. Confirm that the object exists under `S3_PREFIX` and that no upload remains on the API or worker filesystem.

## Rollback

Roll back application services from the Render deploy history. Do not automatically downgrade the database: database rollback is a separate, reviewed operation. If a release contains a breaking schema change, restore the database from a managed backup or execute a tested corrective migration.

## Production checklist

- Use private networking for PostgreSQL and Key Value and keep their public IP allow lists empty.
- Enable PostgreSQL backups and choose retention appropriate for the data.
- Restrict the S3 credentials to the configured bucket and prefix only.
- Configure S3 encryption, lifecycle, versioning, and retention policies as required.
- Configure `SENTRY_DSN`, alerts, log retention, and an external uptime check.
- Rotate JWT, Hugging Face, database, and object-storage credentials periodically.
- Scale the API and worker independently based on request latency and queue depth.
