"""HTTP endpoints: GET /health and POST /analyze-ticket.

Status codes follow Section 4.1: 200 success, 400 malformed/missing required,
422 semantically empty complaint, 500 controlled internal error. The body is
parsed manually so we can return 400 (not FastAPI's default 422) for missing
required fields, and never leak stack traces.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.logging import log_event
from app.engine.analyzer import analyze_ticket
from app.models.schemas import AnalyzeTicketRequest

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/analyze-ticket")
async def analyze(request: Request):
    # 1. Valid JSON object?
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid request body. Please provide valid JSON."},
        )
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "Request body must be a JSON object."},
        )

    # 2. Required fields / types present?
    try:
        payload = AnalyzeTicketRequest(**body)
    except ValidationError:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing or invalid required fields (ticket_id, complaint)."},
        )

    # 3. Semantically usable complaint?
    if not (payload.complaint or "").strip():
        return JSONResponse(
            status_code=422,
            content={"error": "Complaint text is empty."},
        )

    # 4. Analyze (controlled 500 on unexpected failure).
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
