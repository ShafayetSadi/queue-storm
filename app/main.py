"""FastAPI application entrypoint.

Registers the routes and safe exception handlers. Generic errors return a
non-sensitive JSON body — never a stack trace, token, or secret.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.logging import log_event

app = FastAPI(
    title="QueueStorm Investigator",
    description="AI/API SupportOps copilot for digital finance support agents.",
    version="1.0.0",
)

app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Per the spec, malformed JSON / missing required fields are 400 (not 422).
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid request body. Provide valid JSON with the required "
            "fields (ticket_id, complaint)."
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log_event("unhandled_exception", path=str(request.url.path),
              error=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal error."},
    )


@app.get("/")
def root() -> dict:
    return {
        "service": "QueueStorm Investigator",
        "endpoints": ["GET /health", "POST /analyze-ticket"],
    }
