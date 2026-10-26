"""initial claim and idempotency_record

Squashes the former dcf4d55ed31d (reconstructed baseline) and 7c3e1a9b2f40 (align + idempotency) revisions,
which no database depends on any more.

Revision ID: 715363814a6e
Revises:
Create Date: 2026-10-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "715363814a6e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # timestamptz everywhere: Postgres stores the absolute instant (UTC internally), so now() is
    # correct regardless of the session timezone. Do not use timezone('utc', now()) on these columns.
    op.create_table(
        "claim",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "claim_uuid", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("claim_reference", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="received", nullable=False),
        sa.Column("service_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("status IN ('received', 'in_review', 'closed')", name="ck_claim_status"),
        sa.PrimaryKeyConstraint("id", name="claim_pkey"),
        sa.UniqueConstraint("tenant_id", "claim_reference", name="uq_claim_tenant_reference"),
        sa.UniqueConstraint("claim_uuid", name="uq_claim_uuid"),
    )

    op.create_table(
        "idempotency_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("claim_uuid", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "actor_id", "endpoint", "key", name="uq_idempotency_scope"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("idempotency_record")
    op.drop_table("claim")
