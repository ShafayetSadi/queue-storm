"""Pydantic request/response models and the official enums.

These models lock the API contract: required fields, types, nullability, and
exact enum values from Section 5/6/7 of the problem statement.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Output enums (exact strings; values are what gets serialized) ----------


class EvidenceVerdict(str, Enum):
    consistent = "consistent"
    inconsistent = "inconsistent"
    insufficient_data = "insufficient_data"


class CaseType(str, Enum):
    wrong_transfer = "wrong_transfer"
    payment_failed = "payment_failed"
    refund_request = "refund_request"
    duplicate_payment = "duplicate_payment"
    merchant_settlement_delay = "merchant_settlement_delay"
    agent_cash_in_issue = "agent_cash_in_issue"
    phishing_or_social_engineering = "phishing_or_social_engineering"
    other = "other"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Department(str, Enum):
    customer_support = "customer_support"
    dispute_resolution = "dispute_resolution"
    payments_ops = "payments_ops"
    merchant_operations = "merchant_operations"
    agent_operations = "agent_operations"
    fraud_risk = "fraud_risk"


# --- Request models ---------------------------------------------------------
# Inputs are validated leniently: optional enum-like fields are typed as plain
# strings so an unexpected value never turns a real ticket into a 400/422. Only
# ticket_id and complaint are truly required.


class TransactionEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_id: Optional[str] = None
    timestamp: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    counterparty: Optional[str] = None
    status: Optional[str] = None


class AnalyzeTicketRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    complaint: str
    language: Optional[str] = None
    channel: Optional[str] = None
    user_type: Optional[str] = None
    campaign_context: Optional[str] = None
    transaction_history: list[TransactionEntry] = Field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None


# --- Response model ---------------------------------------------------------


class AnalyzeTicketResponse(BaseModel):
    # Serialize enums by value and keep field order matching the spec example.
    model_config = ConfigDict(use_enum_values=True)

    ticket_id: str
    relevant_transaction_id: Optional[str]
    evidence_verdict: EvidenceVerdict
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: Optional[float] = None
    reason_codes: Optional[list[str]] = None


class HealthResponse(BaseModel):
    status: str = "ok"
