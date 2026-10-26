import logging
from typing import Any

import structlog

from .config import settings


def add_correlation_id(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Structlog processor that injects the correlation_id from contextvars.
    """
    try:
        from .middleware.correlation import correlation_id_var

        event_dict["correlation_id"] = correlation_id_var.get()
    except ImportError:
        event_dict["correlation_id"] = "unknown"
    return event_dict


def configure_logging():
    """
    Configures structlog for JSON logging.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            add_correlation_id,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Initialize logging
configure_logging()
logger = structlog.get_logger()

# Add global context
logger.bind(service="mini-claims-api", environment=settings.APP_ENV)
