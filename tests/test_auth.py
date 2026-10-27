from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import SecretStr

from services.claims.app.api.deps import RequestContext, require_permission
from services.claims.app.core import demo_auth
from services.claims.app.core.config import settings
from services.claims.app.core.error_handlers import domain_exception_handler
from services.claims.app.core.exceptions import DomainException, Forbidden

TEST_SECRET = "test-only-secret-" + "x" * 32  # noqa: S105 - synthetic key for tests, not a credential

app = FastAPI()
app.add_exception_handler(DomainException, domain_exception_handler)


@app.post("/create")
def create(ctx: Annotated[RequestContext, Depends(require_permission("claim.create"))]) -> dict[str, str]:
    return {"tenant_id": ctx.tenant_id, "user_id": ctx.user_id}


client = TestClient(app)


@pytest.fixture(autouse=True)
def demo_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEMO_JWT_SECRET", SecretStr(TEST_SECRET))


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _raw_token(secret: str = TEST_SECRET, algorithm: str = "HS256", **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": demo_auth.ISSUER,
        "aud": demo_auth.AUDIENCE,
        "sub": "user-1",
        "tid": "tenant-a",
        "roles": ["claims_submitter"],
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, secret, algorithm=algorithm)


def _assert_forbidden(response: Response, message: str) -> None:
    assert response.status_code == 403
    assert response.json()["error"] == {"code": "forbidden", "message": message, "correlation_id": "unknown"}


def test_valid_token_identity_comes_from_claims() -> None:
    token = demo_auth.issue_demo_token("tenant-a", "user-1", ["claims_submitter"])

    response = client.post("/create", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == {"tenant_id": "tenant-a", "user_id": "user-1"}


def test_role_without_permission_is_denied() -> None:
    token = demo_auth.issue_demo_token("tenant-a", "user-1", ["claims_reader"])

    _assert_forbidden(client.post("/create", headers=_bearer(token)), "Missing required permission.")


def test_unknown_role_grants_nothing() -> None:
    token = _raw_token(roles=["superuser", "claim.create"])

    _assert_forbidden(client.post("/create", headers=_bearer(token)), "Missing required permission.")


def test_permissions_claim_in_token_is_ignored() -> None:
    # A caller cannot grant itself permissions: only roles are read, and only the server maps them.
    token = _raw_token(roles=[], permissions=["claim.create"])

    _assert_forbidden(client.post("/create", headers=_bearer(token)), "Missing required permission.")


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}])
def test_missing_or_non_bearer_token_is_denied(headers: dict[str, str]) -> None:
    _assert_forbidden(client.post("/create", headers=headers), "Missing bearer token.")


@pytest.mark.parametrize(
    "token",
    [
        _raw_token(secret="another-secret-" + "y" * 32),
        _raw_token(exp=datetime.now(UTC) - timedelta(seconds=1)),
        _raw_token(aud="some-other-api"),
        _raw_token(iss="someone-else"),
        _raw_token(exp=None),
        _raw_token(sub=None),
        _raw_token(tid=None),
        _raw_token(tid="tenant a; drop"),
        _raw_token(roles="claims_submitter"),
        "not.a.jwt",
    ],
    ids=[
        "bad-signature",
        "expired",
        "wrong-aud",
        "wrong-iss",
        "no-exp",
        "no-sub",
        "no-tid",
        "bad-tid",
        "roles-str",
        "garbage",
    ],
)
def test_invalid_tokens_are_denied(token: str) -> None:
    _assert_forbidden(client.post("/create", headers=_bearer(token)), "Invalid or expired token.")


def test_alg_none_token_is_denied() -> None:
    now = datetime.now(UTC)
    unsigned = jwt.encode(
        {
            "iss": demo_auth.ISSUER,
            "aud": demo_auth.AUDIENCE,
            "sub": "a",
            "tid": "t",
            "roles": ["claims_submitter"],
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        key=None,
        algorithm="none",
    )

    _assert_forbidden(client.post("/create", headers=_bearer(unsigned)), "Invalid or expired token.")


def test_valid_token_is_refused_outside_local_and_test(monkeypatch: pytest.MonkeyPatch) -> None:
    token = demo_auth.issue_demo_token("tenant-a", "user-1", ["claims_submitter"])
    monkeypatch.setattr(settings, "APP_ENV", "prod")

    _assert_forbidden(
        client.post("/create", headers=_bearer(token)), "Demo authentication is disabled in this environment."
    )


@pytest.mark.parametrize("secret", [None, SecretStr(""), SecretStr("short")])
def test_missing_or_weak_secret_fails_closed(monkeypatch: pytest.MonkeyPatch, secret: SecretStr | None) -> None:
    monkeypatch.setattr(settings, "DEMO_JWT_SECRET", secret)

    _assert_forbidden(client.post("/create", headers=_bearer(_raw_token())), "Demo authentication is not configured.")


def test_issuing_is_refused_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "prod")

    with pytest.raises(Forbidden):
        demo_auth.issue_demo_token("tenant-a", "user-1", ["claims_submitter"])


def test_role_mapping_union() -> None:
    assert demo_auth.permissions_for(["claims_reader", "claims_submitter"]) == {"claim.read", "claim.create"}
    assert demo_auth.permissions_for([]) == frozenset()
