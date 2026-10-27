from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ....api.deps import IdempotencyContext, RequestContext, require_idempotency, require_permission
from ....core.db import get_db
from ....schemas.claim import ClaimCreate, ClaimListResponse, ClaimResponse
from ....services.claim_service import ClaimService

router = APIRouter()

# Annotated dependency avoids calling Depends() in argument defaults (ruff B008).
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ClaimResponse,
)
def create_claim(
    payload: ClaimCreate,
    db: DbSession,
    # ctx before the key: dependencies resolve in order, so unauthenticated callers get 403 before input validation.
    ctx: Annotated[RequestContext, Depends(require_permission("claim.create"))],
    idempotency: Annotated[IdempotencyContext, Depends(require_idempotency)],
):
    """
    Create a new claim.

    Requires `Idempotency-Key` header to prevent duplicate submissions.
    Returns 201 on first success, or 200 if returning a previous result.
    """
    service = ClaimService(db, ctx.tenant_id, ctx.user_id)
    return service.create_claim(payload, idempotency.key, idempotency.endpoint)


@router.get("/{claim_uuid}", response_model=ClaimResponse)
def get_claim(
    claim_uuid: UUID,
    db: DbSession,
    ctx: Annotated[RequestContext, Depends(require_permission("claim.read"))],
):
    """
    Retrieve detailed information for a specific claim.
    """
    service = ClaimService(db, ctx.tenant_id, ctx.user_id)
    return service.get_claim(claim_uuid)


@router.get("/", response_model=ClaimListResponse)
def list_claims(
    db: DbSession,
    ctx: Annotated[RequestContext, Depends(require_permission("claim.read"))],
    page: Annotated[int, Query(ge=1, description="Page number, starting at 1")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Number of items per page")] = 50,
):
    """
    List all claims for the authenticated tenant.
    """
    service = ClaimService(db, ctx.tenant_id, ctx.user_id)
    items, total = service.list_claims(page, page_size)

    return ClaimListResponse(items=items, page=page, page_size=page_size, total=total)
