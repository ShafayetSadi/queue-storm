"""HTTP endpoints: GET /health and POST /analyze-ticket.

The request body is declared as ``AnalyzeTicketRequest`` so the OpenAPI/Swagger
docs render every field. Status codes follow Section 4.1: 200 success, 400
malformed/missing required (mapped from FastAPI's validation error in
``app.main``), 422 semantically empty complaint, 500 controlled internal error.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.logging import log_event
from app.engine.analyzer import analyze_ticket
from app.models.schemas import AnalyzeTicketRequest, AnalyzeTicketResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> dict:
    return {"status": "ok"}


@router.post(
    "/analyze-ticket",
    response_model=AnalyzeTicketResponse,
    responses={
        400: {"description": "Malformed JSON or missing required fields."},
        422: {"description": "Schema valid but complaint is semantically empty."},
        500: {"description": "Controlled internal error (no sensitive details)."},
    },
)
def analyze(payload: AnalyzeTicketRequest):
    # Schema is already validated by FastAPI (400 via the validation handler).
    # Only the semantic check remains: an empty complaint -> 422.
    if not (payload.complaint or "").strip():
        return JSONResponse(
            status_code=422,
            content={"error": "Complaint text is empty."},
        )

    try:
        result = analyze_ticket(payload)
    except Exception as exc:  # pragma: no cover - defensive
        log_event("analyze_unhandled_error", ticket_id=payload.ticket_id,
                  error=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal error while analyzing the ticket."},
        )

    return JSONResponse(status_code=200, content=result.model_dump())
