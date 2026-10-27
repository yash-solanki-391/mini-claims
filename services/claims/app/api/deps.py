"""
Request identity and permission dependencies.

DEMO AUTHENTICATION ONLY - NOT PRODUCTION AUTH. Identity comes from a signed demo token
(`Authorization: Bearer <token>`, see app/core/demo_auth.py), accepted only when APP_ENV is `local` or `test`.
The real AtlasIQ service uses the approved shared auth library.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.demo_auth import permissions_for, verify_demo_token
from ..core.exceptions import Forbidden

# auto_error=False: a missing token is reported through the standard error shape, not FastAPI's default 403 body.
_bearer = HTTPBearer(auto_error=False, description="Demo token (local/test only). NOT production auth.")


@dataclass(frozen=True)
class RequestContext:
    """
    Trusted identity for one request. The only source of tenant and actor for services.
    """

    tenant_id: str
    actor_id: str
    permissions: frozenset[str]


def get_request_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> RequestContext:
    """
    Build the RequestContext from a verified demo token. Fails closed outside local/test.

    Tenant and actor come only from signed claims; permissions come from the server's role mapping,
    so nothing the client asserts about itself is trusted.
    """
    if credentials is None:
        raise Forbidden("Missing bearer token.")

    claims = verify_demo_token(credentials.credentials)
    return RequestContext(
        tenant_id=claims["tid"], actor_id=claims["sub"], permissions=permissions_for(claims.get("roles", []))
    )


def require_permission(permission: str) -> Callable[[RequestContext], RequestContext]:
    """
    Dependency factory: deny the request unless the caller holds `permission`.

    Returns the RequestContext so an endpoint can declare it once and pass tenant/actor to the service.
    """

    def dependency(ctx: Annotated[RequestContext, Depends(get_request_context)]) -> RequestContext:
        if permission not in ctx.permissions:
            raise Forbidden("Missing required permission.")
        return ctx

    return dependency
