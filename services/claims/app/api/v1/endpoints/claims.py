from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from ....api.deps import require_permission
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
    dependencies=[Depends(require_permission("claim.create"))],
)
def create_claim(
    payload: ClaimCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    db: DbSession,
):
    """
    Create a new claim.

    Requires `Idempotency-Key` header to prevent duplicate submissions.
    Returns 201 on first success, or 200 if returning a previous result.
    """
    # Validate Idempotency-Key constraints
    if not idempotency_key.strip() or len(idempotency_key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key must be non-blank and max 128 characters."
        )

    service = ClaimService(db)

    # The endpoint path is used as part of the idempotency key scope
    endpoint = "/v1/claims"

    return service.create_claim(payload, idempotency_key, endpoint)


@router.get("/{claim_uuid}", response_model=ClaimResponse, dependencies=[Depends(require_permission("claim.read"))])
def get_claim(claim_uuid: UUID, db: DbSession):
    """
    Retrieve detailed information for a specific claim.
    """
    service = ClaimService(db)
    return service.get_claim(claim_uuid)


@router.get("/", response_model=ClaimListResponse, dependencies=[Depends(require_permission("claim.read"))])
def list_claims(
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="Page number, starting at 1")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Number of items per page")] = 50,
):
    """
    List all claims for the authenticated tenant.
    """
    service = ClaimService(db)
    items, total = service.list_claims(page, page_size)

    return ClaimListResponse(items=items, page=page, page_size=page_size, total=total)
