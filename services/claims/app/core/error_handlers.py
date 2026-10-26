from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..schemas.error import ErrorOut
from .exceptions import Conflict, DomainException, Forbidden, NotFound, ValidationFailed
from .logging import logger


def domain_exception_handler(request: Request, exc: DomainException):
    """
    Central handler for domain exceptions.
    Maps domain exceptions to their corresponding HTTP status codes.
    """
    # Map exception type to status code
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, NotFound):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, Conflict):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, ValidationFailed):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, Forbidden):
        status_code = status.HTTP_403_FORBIDDEN

    # Use the correlation_id from exception or fallback to request state
    correlation_id = exc.correlation_id or getattr(request.state, "correlation_id", "unknown")

    return JSONResponse(
        status_code=status_code,
        content=ErrorOut(
            error={"code": exc.code, "message": exc.message, "correlation_id": correlation_id}
        ).model_dump(),
    )


def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Normalizes FastAPI request validation errors to the standard ErrorOut shape.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")

    # Consolidate multiple validation errors into one message
    error_msgs = [f"{err['loc']}: {err['msg']}" for err in exc.errors()]
    message = "; ".join(error_msgs)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorOut(
            error={"code": "validation_failed", "message": message, "correlation_id": correlation_id}
        ).model_dump(),
    )


def generic_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unhandled exceptions.
    Returns a generic 500 error and logs the actual exception.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")

    # Log the actual exception with full traceback
    logger.error("unhandled_exception", error=str(exc), correlation_id=correlation_id, exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorOut(
            error={
                "code": "internal_server_error",
                "message": "An unexpected error occurred. Please provide the correlation ID to support.",
                "correlation_id": correlation_id,
            }
        ).model_dump(),
    )


def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handler for standard Starlette/FastAPI HTTPExceptions.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorOut(
            error={"code": "http_error", "message": exc.detail, "correlation_id": correlation_id}
        ).model_dump(),
    )
