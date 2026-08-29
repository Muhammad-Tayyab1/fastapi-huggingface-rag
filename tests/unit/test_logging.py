import json
import logging

from app.core.logging import JsonFormatter
from app.core.request_context import request_id_context


def test_json_logs_include_request_context() -> None:
    token = request_id_context.set("request-123")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="request completed",
            args=(),
            exc_info=None,
        )
        record.method = "GET"
        record.path = "/health"
        record.status_code = 200
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)
    assert payload["request_id"] == "request-123"
    assert payload["status_code"] == 200
