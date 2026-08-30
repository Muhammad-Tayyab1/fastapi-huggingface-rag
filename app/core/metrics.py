from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "rag_api_http_requests_total",
    "HTTP requests processed",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "rag_api_http_request_duration_seconds",
    "HTTP request latency",
    ("method", "route"),
)
RAG_QUERIES = Counter(
    "rag_api_queries_total",
    "RAG query outcomes",
    ("transport", "outcome"),
)
PROVIDER_REQUESTS = Counter(
    "rag_api_provider_requests_total",
    "Hugging Face provider request attempts",
    ("operation", "outcome"),
)
INGESTION_JOBS = Counter(
    "rag_api_ingestion_jobs_total",
    "Document ingestion job outcomes",
    ("outcome",),
)
INGESTION_DURATION = Histogram(
    "rag_api_ingestion_duration_seconds",
    "Document ingestion job duration",
)
ARQ_QUEUE_DEPTH = Gauge(
    "rag_api_arq_queue_depth",
    "Current number of jobs in the configured ARQ queue",
)
QUEUE_SCRAPE_FAILURES = Counter(
    "rag_api_queue_metric_failures_total",
    "Failures while reading ARQ queue depth",
)
