from collections.abc import Iterator

import pytest
import structlog
from fastapi.testclient import TestClient
from starlette.requests import Request
from structlog.testing import capture_logs
from structlog.typing import EventDict

from services.claims.app.core.error_handlers import generic_exception_handler
from services.claims.main import app

client = TestClient(app)


@pytest.fixture
def logs() -> Iterator[list[EventDict]]:
    # merge_contextvars stays in the pipeline so captured events carry the per-request correlation_id.
    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as captured:
        yield captured


def _events(logs: list[EventDict], name: str) -> list[EventDict]:
    return [entry for entry in logs if entry["event"] == name]


def test_valid_correlation_id_is_echoed_and_logged(logs: list[EventDict]) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "req-abc_123"})

    assert response.headers["X-Correlation-ID"] == "req-abc_123"
    [entry] = _events(logs, "request_completed")
    assert entry["correlation_id"] == "req-abc_123"
    assert entry["method"] == "GET"
    assert entry["path"] == "/health"
    assert entry["status_code"] == 200
    assert entry["service"] == "mini-claims-api"


@pytest.mark.parametrize("bad_id", ["has space", "x" * 65, "semi;colon"])
def test_invalid_correlation_id_is_replaced(bad_id: str) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": bad_id})

    returned = response.headers["X-Correlation-ID"]
    assert returned != bad_id
    assert len(returned) == 36  # freshly minted uuid4


def test_error_body_uses_same_correlation_id_as_header() -> None:
    # No demo identity headers -> 403 from require_permission, before any DB access.
    response = client.get("/v1/claims/", headers={"X-Correlation-ID": "err-cid-1"})

    assert response.status_code == 403
    assert response.headers["X-Correlation-ID"] == "err-cid-1"
    assert response.json()["error"]["correlation_id"] == "err-cid-1"


def test_request_log_omits_headers_and_query(logs: list[EventDict]) -> None:
    # An unverifiable bearer token -> 403 before any DB access; the Authorization header is still on the request.
    client.get(
        "/v1/claims/?page=1&secret_q=SHOULD-NOT-LOG",
        headers={"Authorization": "Bearer TOKEN-SHOULD-NOT-LOG"},
    )

    [entry] = _events(logs, "request_completed")
    assert entry["path"] == "/v1/claims/"
    assert "SHOULD-NOT-LOG" not in str(logs)


def test_unhandled_exception_logs_type_not_message(logs: list[EventDict]) -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "state": {"correlation_id": "c1"}})
    try:
        raise ValueError("DEMO-PHI-VALUE")
    except ValueError as exc:
        response = generic_exception_handler(request, exc)

    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == "c1"
    assert b"DEMO-PHI-VALUE" not in response.body
    [entry] = _events(logs, "unhandled_exception")
    assert entry["error_type"] == "ValueError"
    assert entry["frames"]
    assert "DEMO-PHI-VALUE" not in str(entry)
