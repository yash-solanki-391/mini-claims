import logging

import structlog

from .config import settings


def configure_logging() -> None:
    """
    Configures structlog for JSON logging.

    correlation_id reaches every log line through merge_contextvars: CorrelationIdMiddleware binds it per request.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[settings.LOG_LEVEL]),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Initialize logging
configure_logging()

# bind() returns a new logger, so the global context only applies when the bound logger is the one exported.
logger = structlog.get_logger().bind(service="mini-claims-api", environment=settings.APP_ENV)
