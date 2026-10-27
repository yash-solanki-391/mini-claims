"""
Demo token issuing and verification.

DEMO AUTHENTICATION ONLY - NOT PRODUCTION AUTH. A deliberate, learning-only deviation from the standard
"only the shared auth library, no custom token handling" (see docs/adr/0003-demo-jwt-authentication.md).
Works only when APP_ENV is `local` or `test`; the real AtlasIQ service uses the approved shared auth library.

Mint a token locally:
    uv run python -m services.claims.app.core.demo_auth --tenant tenant-a --actor actor-1 --role claims_submitter
"""

import argparse
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from .config import settings
from .exceptions import Forbidden
from .logging import logger

_DEMO_AUTH_ENVS = frozenset({"local", "test"})
_ALGORITHM = "HS256"
# RFC 7518 requires an HS256 key of at least 256 bits; shorter keys are brute-forceable.
_MIN_SECRET_LENGTH = 32

ISSUER = "mini-claims-demo-issuer"
AUDIENCE = "mini-claims-api"

# Identifiers end up in DB columns (tenant_id, created_by) and log context, so only a safe, bounded charset passes.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

# The server, not the token, decides what a role may do. Unknown roles grant nothing.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "claims_reader": frozenset({"claim.read"}),
    "claims_submitter": frozenset({"claim.read", "claim.create"}),
}


def _secret() -> str:
    if settings.APP_ENV not in _DEMO_AUTH_ENVS:
        raise Forbidden("Demo authentication is disabled in this environment.")
    secret = settings.DEMO_JWT_SECRET.get_secret_value() if settings.DEMO_JWT_SECRET else ""
    if len(secret) < _MIN_SECRET_LENGTH:
        raise Forbidden("Demo authentication is not configured.")
    return secret


def issue_demo_token(tenant_id: str, actor_id: str, roles: list[str], ttl: timedelta = timedelta(hours=1)) -> str:
    """Sign a demo token. Refuses outside local/test, like verification."""
    now = datetime.now(UTC)
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": actor_id, "tid": tenant_id, "roles": roles, "iat": now}
    return jwt.encode({**claims, "exp": now + ttl}, _secret(), algorithm=_ALGORITHM)


def verify_demo_token(token: str) -> dict[str, Any]:
    """
    Verify signature, expiry, issuer and audience, then validate the identity claims.

    Every failure is the same Forbidden so callers cannot probe which check failed; the reason is logged
    as an exception type only, never the token.
    """
    secret = _secret()
    try:
        # algorithms is pinned so a token cannot choose its own (e.g. "none").
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        logger.info("auth_token_rejected", reason=type(exc).__name__)
        raise Forbidden("Invalid or expired token.") from exc

    tenant_id, actor_id, roles = claims.get("tid"), claims.get("sub"), claims.get("roles", [])
    if not (
        isinstance(tenant_id, str)
        and _IDENTIFIER_PATTERN.match(tenant_id)
        and isinstance(actor_id, str)
        and _IDENTIFIER_PATTERN.match(actor_id)
        and isinstance(roles, list)
        and all(isinstance(role, str) for role in roles)
    ):
        logger.info("auth_token_rejected", reason="InvalidClaims")
        raise Forbidden("Invalid or expired token.")
    return claims


def permissions_for(roles: list[str]) -> frozenset[str]:
    """Union of the permissions the server grants each known role."""
    return frozenset().union(*(ROLE_PERMISSIONS.get(role, frozenset()) for role in roles))


def _main() -> None:
    parser = argparse.ArgumentParser(description="Mint a local/test-only demo token (NOT production auth).")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--role", action="append", default=[], choices=sorted(ROLE_PERMISSIONS), dest="roles")
    parser.add_argument("--ttl-minutes", type=int, default=60)
    args = parser.parse_args()
    for value in (args.tenant, args.actor):
        if not _IDENTIFIER_PATTERN.match(value):
            parser.error(f"invalid identifier: {value!r} (allowed: A-Z a-z 0-9 _ . -, max 64)")
    try:
        token = issue_demo_token(args.tenant, args.actor, args.roles, timedelta(minutes=args.ttl_minutes))
    except Forbidden as exc:
        parser.exit(1, f"error: {exc.message}\n")
    print(token)


if __name__ == "__main__":
    _main()
