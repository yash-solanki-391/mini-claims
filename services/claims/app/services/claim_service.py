from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.exceptions import Conflict, NotFound
from ..core.logging import logger
from ..models.claim import Claim
from ..models.idempotency import IdempotencyRecord
from ..schemas.claim import ClaimCreate, ClaimResponse
from ..utils.hashing import calculate_request_hash

# Only the columns ClaimResponse needs; avoids loading full rows for reads and lists.
_RESPONSE_COLUMNS = (Claim.claim_uuid, Claim.claim_reference, Claim.status, Claim.service_date, Claim.created_at)


def _to_response(row: Any) -> ClaimResponse:
    # ClaimResponse.uuid is typed str, so the UUID is converted explicitly rather than via from_attributes.
    return ClaimResponse.model_validate(
        {
            "claim_uuid": str(row.claim_uuid),
            "claim_reference": row.claim_reference,
            "status": row.status,
            "service_date": row.service_date,
            "created_at": row.created_at,
        }
    )


class ClaimService:
    """
    Claim business logic. Tenant and user are supplied by the caller from RequestContext,
    never from the request body, path or query.
    """

    def __init__(self, db: Session, tenant_id: str, user_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

    def create_claim(self, payload: ClaimCreate, idempotency_key: str, endpoint: str) -> ClaimResponse:
        """
        Create a claim idempotently.

        Same key + same payload returns the original claim; same key + different payload raises Conflict.
        """
        request_hash = calculate_request_hash(payload)

        try:
            # Lookup and writes share one transaction so the claim and its idempotency record commit together.
            with self.db.begin():
                existing = self.db.scalars(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.tenant_id == self.tenant_id,
                        IdempotencyRecord.user_id == self.user_id,
                        IdempotencyRecord.endpoint == endpoint,
                        IdempotencyRecord.key == idempotency_key,
                    )
                ).first()

                if existing is not None:
                    if existing.request_hash != request_hash:
                        raise Conflict("Idempotency-Key was already used with a different payload.")
                    return self._get_response(existing.claim_uuid)

                claim = Claim(
                    tenant_id=self.tenant_id,
                    claim_reference=payload.claim_reference,
                    status=payload.status,
                    service_date=payload.service_date,
                    created_by=self.user_id,
                    updated_by=self.user_id,
                )
                self.db.add(claim)
                # Flush to obtain the server-generated claim_uuid for the idempotency record.
                self.db.flush()

                self.db.add(
                    IdempotencyRecord(
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                        endpoint=endpoint,
                        key=idempotency_key,
                        request_hash=request_hash,
                        claim_uuid=claim.claim_uuid,
                    )
                )
                # Build the response before commit expires the instance and forces a reload.
                response = _to_response(claim)
        except IntegrityError as exc:
            # uq_claim_tenant_reference: the reference already exists for this tenant.
            raise Conflict("A claim with this claim_reference already exists.") from exc

        logger.info("claim_created", claim_uuid=response.uuid)
        return response

    def get_claim(self, claim_uuid: UUID) -> ClaimResponse:
        """
        Return one claim for the current tenant. Other tenants' claims raise NotFound, never Forbidden.
        """
        return self._get_response(claim_uuid)

    def list_claims(self, page: int, page_size: int) -> tuple[list[ClaimResponse], int]:
        """
        Return one page of the current tenant's claims, newest first, and the tenant's total count.
        """
        tenant_filter = Claim.tenant_id == self.tenant_id

        rows = self.db.execute(
            select(*_RESPONSE_COLUMNS)
            .where(tenant_filter)
            # id breaks ties so pagination is stable when created_at values collide.
            .order_by(Claim.created_at.desc(), Claim.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        ).all()
        total = self.db.scalar(select(func.count()).select_from(Claim).where(tenant_filter)) or 0

        return [_to_response(row) for row in rows], total

    def _get_response(self, claim_uuid: UUID) -> ClaimResponse:
        row = self.db.execute(
            select(*_RESPONSE_COLUMNS).where(Claim.tenant_id == self.tenant_id, Claim.claim_uuid == claim_uuid)
        ).first()
        if row is None:
            raise NotFound("Claim not found.")
        return _to_response(row)
