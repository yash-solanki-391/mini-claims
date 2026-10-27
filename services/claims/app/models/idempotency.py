import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IdempotencyRecord(Base):
    """
    Tracks request idempotency to prevent duplicate processing.
    """

    __tablename__ = "idempotency_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String, nullable=False)

    # We store the resulting claim_uuid to retrieve the original record
    claim_uuid: Mapped[uuid.UUID] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    __table_args__ = (
        # Idempotency scope is tenant + user + endpoint + key: different tenants/users never collide on a key,
        # and concurrent retries of the same request cannot both insert. The constraint's index also serves the lookup.
        UniqueConstraint("tenant_id", "user_id", "endpoint", "key", name="uq_idempotency_scope"),
    )
