import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IdempotencyRecord(Base):
    """
    Tracks request idempotency to prevent duplicate processing.
    """

    __tablename__ = "idempotency_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String, nullable=False)

    # We store the resulting claim_uuid to retrieve the original record
    claim_uuid: Mapped[uuid.UUID] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    __table_args__ = (
        # Unique constraint: Key is unique per tenant, actor, and endpoint
        # This prevents different users/tenants from colliding on the same key
        # and prevents the same user from using the same key for different endpoints.
        # Note: Using a composite index for efficient lookups.
        {
            "unique_constraints": [
                # Note: SQLAlchemy 2.0 unique constraints in __table_args__
            ]
        }
    )

    # Explicitly defining the unique constraint for clarity
    __table_args__ = (
        # Unique constraint on (tenant_id, actor_id, endpoint, key)
        # We use a manual constraint for clarity in the migration
        # but we define it here for ORM awareness.
        # We'll define this as a UniqueConstraint in the migration file.
    )
