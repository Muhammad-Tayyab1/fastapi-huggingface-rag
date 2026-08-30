import json
from pathlib import Path


def test_grafana_dashboard_has_unique_panels_and_prometheus_queries() -> None:
    dashboard = json.loads(Path("observability/grafana-dashboard.json").read_text(encoding="utf-8"))
    panels = dashboard["panels"]

    assert dashboard["uid"] == "fastapi-hf-rag"
    assert len({panel["id"] for panel in panels}) == len(panels)
    assert all(panel["targets"] for panel in panels)
    expressions = " ".join(target["expr"] for panel in panels for target in panel["targets"])
    assert "rag_api_http_requests_total" in expressions
    assert "rag_api_queries_total" in expressions
    assert "rag_api_provider_requests_total" in expressions
    assert "rag_api_ingestion_jobs_total" in expressions
    assert "rag_api_arq_queue_depth" in expressions
