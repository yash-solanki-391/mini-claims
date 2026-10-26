"""
Request identity and permission dependencies.

DEMO AUTHENTICATION ONLY - NOT PRODUCTION AUTH. Identity is read from controlled `X-Demo-*` headers and is
accepted only when APP_ENV is `local` or `test`. The real AtlasIQ service uses the approved shared auth library.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header

from ..core.config import settings
from ..core.exceptions import Forbidden

_DEMO_AUTH_ENVS = frozenset({"local", "test"})

# Header values end up in DB columns (created_by, tenant_id) and log context, so only a safe, bounded charset passes.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_PERMISSION_PATTERN = re.compile(r"^[a-z_]+\.[a-z_]+$")


@dataclass(frozen=True)
class RequestContext:
    """
    Trusted identity for one request. The only source of tenant and actor for services.
    """

    tenant_id: str
    actor_id: str
    permissions: frozenset[str]


def get_request_context(
    tenant_id: Annotated[str | None, Header(alias="X-Demo-Tenant-Id")] = None,
    actor_id: Annotated[str | None, Header(alias="X-Demo-Actor-Id")] = None,
    permissions: Annotated[str | None, Header(alias="X-Demo-Permissions")] = None,
) -> RequestContext:
    """
    Build the RequestContext from demo headers. Fails closed outside local/test.

    Errors never echo header values, so identity data cannot leak into responses or logs.
    """
    if settings.APP_ENV not in _DEMO_AUTH_ENVS:
        raise Forbidden("Demo authentication is disabled in this environment.")

    if not tenant_id or not _IDENTIFIER_PATTERN.match(tenant_id):
        raise Forbidden("Missing or invalid tenant identity.")
    if not actor_id or not _IDENTIFIER_PATTERN.match(actor_id):
        raise Forbidden("Missing or invalid actor identity.")

    granted = frozenset(p.strip() for p in (permissions or "").split(",") if p.strip())
    if any(not _PERMISSION_PATTERN.match(p) for p in granted):
        raise Forbidden("Invalid permissions.")

    return RequestContext(tenant_id=tenant_id, actor_id=actor_id, permissions=granted)


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
