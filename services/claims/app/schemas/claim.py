from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClaimCreate(BaseModel):
    """
    Schema for creating a new claim.
    Strictly forbids extra fields to prevent payload injection.
    """

    claim_reference: str = Field(..., min_length=1, max_length=64, description="The external reference for the claim")
    status: str = Field("received", pattern=r"^(received|in_review|closed)$", description="The status of the claim")
    service_date: datetime | None = Field(None, description="The date the service was provided")

    model_config = ConfigDict(extra="forbid")


class ClaimResponse(BaseModel):
    """
    Schema for returning a single claim.
    Maps 'claim_uuid' from the model to 'uuid' in the API response.
    """

    uuid: str = Field(..., validation_alias="claim_uuid")
    claim_reference: str
    status: str
    service_date: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClaimListResponse(BaseModel):
    """
    Schema for paginated list of claims.
    """

    items: list[ClaimResponse]
    page: int
    page_size: int
    total: int
