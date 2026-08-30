# Observability and incident response

The repository ships a Prometheus rule group, a scrape configuration example, and an importable Grafana dashboard in `observability/`. These assets use only the bounded-label metrics exposed by the API.

## Install

1. Enable API metrics with `METRICS_ENABLED=true` and set a strong `METRICS_BEARER_TOKEN` on every metrics-producing API instance.
2. Store that same token in a file readable only by Prometheus. Do not put it directly in Prometheus YAML or commit it.
3. Copy `observability/prometheus.example.yml`, update the target for the deployed API, and mount the token at `/run/secrets/rag_metrics_token`.
4. Mount `observability/prometheus-alerts.yml` at `/etc/prometheus/prometheus-alerts.yml` and configure Alertmanager receivers separately.
5. Import `observability/grafana-dashboard.json` and select the Prometheus datasource when prompted.

If the API runs multiple processes or replicas, follow Prometheus Python multiprocess guidance or scrape a single metrics-producing process per container. Verify that queries aggregate all intended instances before relying on alerts.

## SLO starting point

Use these as initial objectives, then tune them from observed traffic and business requirements:

- Availability: at least 99.5% non-5xx responses over 30 days.
- API latency: overall p95 below two seconds, excluding streaming duration when analyzing interactive first-token latency.
- Ingestion reliability: at least 90% of jobs complete successfully over 15-minute active windows.
- Queue health: fewer than 100 waiting jobs for sustained periods.

The bundled rules deliberately require minimum traffic before ratio alerts fire. This avoids division-by-zero noise but does not replace synthetic uptime monitoring for quiet services.

## Triage order

### Target down or high 5xx ratio

1. Check `/api/v1/health` and `/api/v1/ready` from the same network as Prometheus.
2. Inspect recent deploys, application logs by request ID, and Sentry errors.
3. Check PostgreSQL and Redis health, connection limits, CPU, memory, and storage.
4. Roll back the application release if the incident began directly after deployment. Do not downgrade the database automatically.

### Provider errors or high latency

1. Split `rag_api_provider_requests_total` by `operation` to identify embeddings, chat, streaming chat, or reranking.
2. Check Hugging Face provider status, account quota, model availability, and request latency.
3. Disable optional reranking if it is the failing operation. Preserve the configured fail-open behavior during provider degradation.
4. Reduce ingestion concurrency or RAG rate limits if provider throttling is amplifying retries.

### Ingestion failures or queue backlog

1. Compare ingestion failure rate, duration, and queue depth.
2. Inspect failed job and document error messages without exposing document content in shared channels.
3. Check worker replica health, Redis memory policy, S3 access, Hugging Face embeddings, and PostgreSQL capacity.
4. Scale workers gradually. Confirm provider and database limits before increasing concurrency.

### High no-context ratio

1. Confirm the user's documents reached `ready` state.
2. Compare the timing with model, chunking, retrieval-threshold, hybrid-weight, reranking, or safety-policy changes.
3. Run the versioned evaluation dataset against the affected release.
4. Treat traffic-mix changes as a possible explanation; this alert is informational by default.

## Rule tuning

Validate every rule edit with `promtool check rules observability/prometheus-alerts.yml`. Adjust thresholds and `for` durations in a reviewed change. Route `critical` alerts to a paging receiver, `warning` alerts to the operational channel, and `info` alerts to a non-paging destination. Attach environment and ownership labels in the platform-level Prometheus or Alertmanager configuration rather than adding unbounded application labels.
