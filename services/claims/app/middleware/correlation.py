import re
import uuid
from contextvars import ContextVar

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to store the correlation ID for the request lifecycle
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="unknown")

# Regex for validating correlation ID: alphanumeric, dashes, and underscores, max 64 chars
CORRELATION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle X-Correlation-ID for request tracing.
    """

    async def dispatch(self, request: Request, call_next):
        incoming_id = request.headers.get("X-Correlation-ID")

        # Untrusted header: accept only if it matches the safe pattern, else mint a fresh id.
        correlation_id = incoming_id if incoming_id and CORRELATION_ID_PATTERN.match(incoming_id) else str(uuid.uuid4())

        # Store in ContextVar for logging and general use
        token = correlation_id_var.set(correlation_id)
        request.state.correlation_id = correlation_id

        # Bind to structlog contextvars for automatic inclusion in logs
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            # Clean up context
            correlation_id_var.reset(token)
            structlog.contextvars.clear_contextvars()
