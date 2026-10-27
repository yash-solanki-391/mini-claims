import re
import time
import uuid
from contextvars import ContextVar

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from ..core.logging import logger

# Context variable to store the correlation ID for the request lifecycle
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="unknown")

# Regex for validating correlation ID: alphanumeric, dashes, and underscores, max 64 chars
CORRELATION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle X-Correlation-ID for request tracing.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = request.headers.get("X-Correlation-ID")

        # Untrusted header: accept only if it matches the safe pattern, else mint a fresh id.
        correlation_id = incoming_id if incoming_id and CORRELATION_ID_PATTERN.match(incoming_id) else str(uuid.uuid4())

        # Store in ContextVar for logging and general use
        token = correlation_id_var.set(correlation_id)
        request.state.correlation_id = correlation_id

        # Bind to structlog contextvars for automatic inclusion in logs
        log_tokens = structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            # Method, path and status only: never query string, headers or body, which may carry identity or PHI.
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            return response
        finally:
            # Clean up context; reset (not clear) so only what this request bound is removed.
            correlation_id_var.reset(token)
            structlog.contextvars.reset_contextvars(**log_tokens)
