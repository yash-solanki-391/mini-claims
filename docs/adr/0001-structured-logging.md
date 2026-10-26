# ADR 001: Structured JSON Logging with structlog

## Status
Accepted

## Context
The Mini Claims API requires structured JSON logging for observability and integration with log management systems. We need to ensure that:
- Logs include a `correlation_id` for request tracing.
- Logs include global context (service name, environment).
- Logs never contain sensitive data (payloads, headers, tokens).
- Logging is high-performance and non-blocking.

## Decision
We will use `structlog` as the primary logging library.

## Rationale
`structlog` is the industry standard for structured logging in Python for several reasons:
1. **Contextual Logging**: It allows us to bind context (like `correlation_id`) to a logger, which is then automatically included in all subsequent log calls.
2. **Processor Pipeline**: The pipeline architecture allows us to easily add, remove, or modify log fields (e.g., adding timestamps, formatting the level) before the log is written.
3. **Performance**: It is designed for high performance and avoids expensive string formatting unless necessary.
4. **JSON Output**: It provides a first-class `JSONRenderer` that ensures logs are valid JSON, making them easily parsable by ELK, Splunk, or Datadog.

## Consequences
- **Dependency**: Adds `structlog` to the project dependencies.
- **Learning Curve**: Developers must use `structlog.get_logger()` instead of the standard `logging` module for new code.
- **Configuration**: Requires a central configuration in `app/core/logging.py` to set up the processor pipeline.
