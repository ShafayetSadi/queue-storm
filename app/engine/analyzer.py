"""Investigation orchestrator.

Flow (single ordered LLM call, deterministic floor):
  normalize -> features -> safety prescan -> deterministic transaction pick ->
  deterministic baseline (always) -> [optional LLM text enrichment, validated] ->
  safety sanitize -> final schema validation.

The deterministic engine owns all scored decision fields. The LLM may only
improve narrative text plus optional confidence / reason codes. If the LLM
fails validation, the deterministic baseline is returned unchanged. Either way
the response is always valid and safe.
"""

from __future__ import annotations

import time
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.logging import log_event
from app.engine import safety
from app.engine.classifier import classify_case
from app.engine.feature_extractor import extract_complaint_features
from app.engine.matcher import MatchResult, select_transaction
from app.engine.normalizer import NormalizedRequest, normalize_request
from app.engine.response_builder import build_text
from app.engine.routing import route_case
from app.engine.verdict import decide_verdict
from app.llm.client import LLMClient
from app.llm.investigator import run_investigator
from app.models.schemas import AnalyzeTicketRequest, AnalyzeTicketResponse
def _deterministic_response(
    norm: NormalizedRequest, features, match: MatchResult
) -> dict:
    case_type, ct_reasons = classify_case(norm, features, match)
    verdict, v_reasons = decide_verdict(norm, features, match, case_type)
    routing = route_case(norm, features, match, case_type, verdict)
    text = build_text(
        norm, features, match, case_type, verdict, routing, ct_reasons + v_reasons
    )
    return {
        "ticket_id": norm.request.ticket_id,
        "relevant_transaction_id": match.relevant_transaction_id,
        "evidence_verdict": verdict,
        "case_type": case_type,
        "severity": routing.severity,
        "department": routing.department,
        "agent_summary": text.agent_summary,
        "recommended_next_action": text.recommended_next_action,
        "customer_reply": text.customer_reply,
        "human_review_required": routing.human_review_required,
        "confidence": text.confidence,
        "reason_codes": text.reason_codes,
    }


def _llm_response(llm: dict, baseline: dict) -> dict:
    response = dict(baseline)
    response["agent_summary"] = llm["agent_summary"]
    response["recommended_next_action"] = llm["recommended_next_action"]
    response["customer_reply"] = llm["customer_reply"]
    if llm.get("confidence") is not None:
        response["confidence"] = llm["confidence"]
    if llm.get("reason_codes"):
        response["reason_codes"] = llm["reason_codes"]
    return response


def analyze_ticket(
    request: AnalyzeTicketRequest,
    settings: Optional[Settings] = None,
    llm_client: Optional[LLMClient] = None,
) -> AnalyzeTicketResponse:
    settings = settings or get_settings()
    started = time.perf_counter()

    norm = normalize_request(request)
    features = extract_complaint_features(norm)
    ctx = safety.prescan(norm, features)
    match = select_transaction(norm, features)

    # Always compute the deterministic baseline (cheap, guarantees a valid result).
    baseline = _deterministic_response(norm, features, match)

    source = "deterministic"
    response = baseline
    if settings.llm_enabled:
        llm = run_investigator(norm, match, client=llm_client)
        if llm is not None:
            response = _llm_response(llm, baseline)
            source = "llm_text"
        else:
            response = baseline
            source = "deterministic_fallback"
            codes = response.get("reason_codes") or []
            if "llm_fallback" not in codes:
                codes.append("llm_fallback")
            response["reason_codes"] = codes

    # Always-on safety sanitizer (final authority over safety).
    response = safety.sanitize(response, ctx)

    # Final schema validation; on any failure fall back to a guaranteed-safe result.
    try:
        validated = AnalyzeTicketResponse(**response)
    except Exception as exc:  # pragma: no cover - defensive
        log_event("schema_validation_failed", ticket_id=request.ticket_id,
                  error=type(exc).__name__)
        safe = safety.sanitize(baseline, ctx)
        validated = AnalyzeTicketResponse(**safe)
        source = "schema_fallback"

    log_event(
        "analyze_ticket",
        ticket_id=request.ticket_id,
        source=source,
        case_type=validated.case_type,
        evidence_verdict=validated.evidence_verdict,
        relevant_transaction_id=validated.relevant_transaction_id,
        severity=validated.severity,
        human_review_required=validated.human_review_required,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return validated
