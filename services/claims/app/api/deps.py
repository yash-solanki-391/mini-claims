"""
Request identity and permission dependencies.

DEMO AUTHENTICATION ONLY - NOT PRODUCTION AUTH. Identity comes from a signed demo token
(`Authorization: Bearer <token>`, see app/core/demo_auth.py), accepted only when APP_ENV is `local` or `test`.
The real AtlasIQ service uses the approved shared auth library.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.demo_auth import permissions_for, verify_demo_token
from ..core.exceptions import Forbidden, ValidationFailed

# auto_error=False: a missing token is reported through the standard error shape, not FastAPI's default 403 body.
_bearer = HTTPBearer(auto_error=False, description="Demo token (local/test only). NOT production auth.")


@dataclass(frozen=True)
class RequestContext:
    """
    Trusted identity for one request. The only source of tenant and user for services.
    """

    tenant_id: str
    user_id: str
    permissions: frozenset[str]


def get_request_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> RequestContext:
    """
    Build the RequestContext from a verified demo token. Fails closed outside local/test.

    Tenant and user come only from signed claims; permissions come from the server's role mapping,
    so nothing the client asserts about itself is trusted.
    """
    if credentials is None:
        raise Forbidden("Missing bearer token.")

    claims = verify_demo_token(credentials.credentials)
    return RequestContext(
        tenant_id=claims["tid"], user_id=claims["sub"], permissions=permissions_for(claims.get("roles", []))
    )


@dataclass(frozen=True)
class IdempotencyContext:
    """
    Validated Idempotency-Key plus the operation it is scoped to.
    """

    key: str
    # Derived per request, never hand-written, so a copy-pasted endpoint cannot share another's key space.
    endpoint: str


def require_idempotency(
    request: Request,
    idempotency_key: Annotated[
        str,
        # max_length is enforced by FastAPI and documented in OpenAPI; a missing header is a standard 422.
        Header(alias="Idempotency-Key", max_length=128, description="Client-generated key, unique per create."),
    ],
) -> IdempotencyContext:
    """
    Validate the Idempotency-Key header and derive its scope once for every create endpoint.

    Whitespace-only keys cannot be expressed as a Header constraint, so they are rejected here.
    """
    if not idempotency_key.strip():
        raise ValidationFailed("Idempotency-Key must be non-blank and max 128 characters.")

    return IdempotencyContext(key=idempotency_key, endpoint=_route_template(request))


def _route_template(request: Request) -> str:
    """
    Full route template of the matched route, e.g. `/v1/claims` or `/v1/claims/{claim_uuid}`.

    The matched route only knows its path inside its own router, so the router prefixes are recovered by
    stripping the part that route produced from the requested path. Only public Starlette APIs are used.
    Templates (not concrete values) keep `/v1/claims/abc` and `/v1/claims/xyz` in one scope.
    """
    route = request.scope["route"]
    path: str = request.scope["path"]
    route_part = str(route.url_path_for(route.name, **request.path_params))
    if not path.endswith(route_part):
        # Never fall back to a guessed scope: a wrong scope silently merges or splits key spaces.
        raise RuntimeError("Cannot derive idempotency scope for the matched route.")
    return (path[: len(path) - len(route_part)] + route.path_format).rstrip("/") or "/"


def require_permission(permission: str) -> Callable[[RequestContext], RequestContext]:
    """
    Dependency factory: deny the request unless the caller holds `permission`.

    Returns the RequestContext so an endpoint can declare it once and pass tenant/user to the service.
    """

    def dependency(ctx: Annotated[RequestContext, Depends(get_request_context)]) -> RequestContext:
        if permission not in ctx.permissions:
            raise Forbidden("Missing required permission.")
        return ctx

    return dependency
