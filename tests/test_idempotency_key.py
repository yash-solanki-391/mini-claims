from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.claims.app.api import deps
from services.claims.app.api.deps import IdempotencyContext, require_idempotency
from services.claims.app.core import demo_auth
from services.claims.app.core.config import settings
from services.claims.app.core.error_handlers import domain_exception_handler, validation_exception_handler
from services.claims.app.core.exceptions import DomainException
from services.claims.main import app

client = TestClient(app)
BODY = {"claim_reference": "DEMO-CLAIM-001"}


@pytest.fixture(autouse=True)
def demo_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEMO_JWT_SECRET", SecretStr("test-only-secret-" + "x" * 32))


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {demo_auth.issue_demo_token('tenant-a', 'user-1', ['claims_submitter'])}"}


@pytest.mark.parametrize("key", ["", "   ", "\t"], ids=["empty", "spaces", "tab"])
def test_blank_key_is_rejected(key: str) -> None:
    response = client.post("/v1/claims/", json=BODY, headers={**_auth(), "Idempotency-Key": key})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_key_over_128_chars_is_rejected() -> None:
    response = client.post("/v1/claims/", json=BODY, headers={**_auth(), "Idempotency-Key": "k" * 129})

    assert response.status_code == 422
    assert "Idempotency-Key" in response.json()["error"]["message"]


def test_missing_key_is_rejected() -> None:
    response = client.post("/v1/claims/", json=BODY, headers=_auth())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_permission_is_checked_before_key() -> None:
    # No token and a blank key: the caller learns nothing about input rules before authenticating.
    response = client.post("/v1/claims/", json=BODY, headers={"Idempotency-Key": "  "})

    assert response.status_code == 403


# Echo app mirroring the real layout (router included under a prefix) to observe the derived scope.
_router = APIRouter()
Idempotency = Annotated[IdempotencyContext, Depends(require_idempotency)]


@_router.post("/")
def create_widget(idempotency: Idempotency) -> dict[str, str]:
    return {"key": idempotency.key, "endpoint": idempotency.endpoint}


@_router.post("/{widget_id}/copies")
def copy_widget(widget_id: str, idempotency: Idempotency) -> dict[str, str]:
    return {"key": idempotency.key, "endpoint": idempotency.endpoint}


echo_app = FastAPI()
echo_app.include_router(_router, prefix="/v1/widgets")
echo_app.add_exception_handler(DomainException, domain_exception_handler)
echo_app.add_exception_handler(RequestValidationError, validation_exception_handler)
echo = TestClient(echo_app)


@pytest.mark.parametrize("key", ["k", "k" * 128, "retry-2026-10-27_01"], ids=["1-char", "128-chars", "typical"])
def test_valid_key_is_passed_through_unchanged(key: str) -> None:
    response = echo.post("/v1/widgets/", headers={"Idempotency-Key": key})

    assert response.status_code == 200
    assert response.json()["key"] == key


def test_scope_is_the_full_route_template() -> None:
    response = echo.post("/v1/widgets/", headers={"Idempotency-Key": "k1"})

    assert response.json()["endpoint"] == "/v1/widgets"


def test_each_route_gets_its_own_scope() -> None:
    create = echo.post("/v1/widgets/", headers={"Idempotency-Key": "k1"}).json()["endpoint"]
    copy = echo.post("/v1/widgets/w-1/copies", headers={"Idempotency-Key": "k1"}).json()["endpoint"]

    assert create != copy


def test_path_values_do_not_change_the_scope() -> None:
    first = echo.post("/v1/widgets/w-1/copies", headers={"Idempotency-Key": "k1"}).json()["endpoint"]
    second = echo.post("/v1/widgets/w-2/copies", headers={"Idempotency-Key": "k1"}).json()["endpoint"]

    assert first == second == "/v1/widgets/{widget_id}/copies"


def test_create_claim_scope_is_passed_to_service(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_create(self: object, payload: object, idempotency_key: str, endpoint: str) -> dict[str, str]:
        captured.update(key=idempotency_key, endpoint=endpoint)
        raise deps.ValidationFailed("stop before DB")

    monkeypatch.setattr("services.claims.app.services.claim_service.ClaimService.create_claim", fake_create)
    client.post("/v1/claims/", json=BODY, headers={**_auth(), "Idempotency-Key": "k-claims"})

    assert captured == {
        "key": "k-claims",
        "endpoint": "/v1/claims",
    }


def test_context_is_immutable() -> None:
    ctx = IdempotencyContext(key="k", endpoint="/v1/x")

    with pytest.raises(AttributeError):
        ctx.endpoint = "/v1/other"  # type: ignore[misc]
