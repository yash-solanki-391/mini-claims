from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.claims.app.api.v1.endpoints import claims
from services.claims.app.core.error_handlers import (
    domain_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from services.claims.app.core.exceptions import Conflict, DomainException, Forbidden, NotFound

app = FastAPI(title="Mini Claims API", description="Learning project practicing AtlasIQ backend standards.")

# --- Error Handlers ---
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(DomainException, domain_exception_handler)
app.add_exception_handler(NotFound, domain_exception_handler)
app.add_exception_handler(Conflict, domain_exception_handler)
app.add_exception_handler(Forbidden, domain_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# --- Routers ---
app.include_router(claims.router, prefix="/v1/claims", tags=["claims"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify the service is running.
    """
    return {"status": "ok"}
