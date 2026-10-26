# Subclass names (NotFound, Conflict, ...) are fixed by the project standards, so the Error suffix is not used.
class DomainException(Exception):  # noqa: N818
    """
    Base class for all domain-specific exceptions.
    """

    def __init__(self, message: str, code: str, correlation_id: str | None = None):
        self.message = message
        self.code = code
        self.correlation_id = correlation_id
        super().__init__(self.message)


class NotFound(DomainException):
    """Resource not found (404)."""

    def __init__(self, message: str = "Resource not found", correlation_id: str | None = None):
        super().__init__(message, "not_found", correlation_id)


class Conflict(DomainException):
    """Resource conflict (409)."""

    def __init__(self, message: str = "Resource conflict", correlation_id: str | None = None):
        super().__init__(message, "conflict", correlation_id)


class ValidationFailed(DomainException):
    """Business validation failed (422)."""

    def __init__(self, message: str = "Validation failed", correlation_id: str | None = None):
        super().__init__(message, "validation_failed", correlation_id)


class Forbidden(DomainException):
    """Access forbidden (403)."""

    def __init__(self, message: str = "Access forbidden", correlation_id: str | None = None):
        super().__init__(message, "forbidden", correlation_id)
