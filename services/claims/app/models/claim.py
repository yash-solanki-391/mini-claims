import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Claim(Base):
    """
    Claim model representing a medical claim.
    """

    __tablename__ = "claim"

    # Publicly exposed ID - renamed from uuid to claim_uuid to avoid module conflict
    claim_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, server_default=text("gen_random_uuid()"), primary_key=False
    )

    # Internal primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Tenancy and reference
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    claim_reference: Mapped[str] = mapped_column(String, nullable=False)

    # Status with constraint: received, in_review, closed
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="received")

    service_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    # Aware UTC on update: a naive datetime.now() is local wall time, which Postgres would misread as UTC.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    created_by: Mapped[str] = mapped_column(String, nullable=False)
    updated_by: Mapped[str] = mapped_column(String, nullable=False)

    # Optimistic locking
    row_version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)

    __table_args__ = (
        # Unique constraint on (tenant_id, claim_reference)
        UniqueConstraint("tenant_id", "claim_reference", name="uq_claim_tenant_reference"),
        # Status check constraint
        CheckConstraint("status IN ('received', 'in_review', 'closed')", name="ck_claim_status"),
    )

    def __repr__(self) -> str:
        return f"<Claim(uuid={self.claim_uuid}, reference={self.claim_reference}, status={self.status})>"
