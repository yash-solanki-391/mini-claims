from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str


class ErrorOut(BaseModel):
    """
    Standard error response shape.
    """

    error: ErrorDetail
