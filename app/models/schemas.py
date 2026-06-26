"""Pydantic request/response models and the official enums.

These models lock the API contract: required fields, types, nullability, and
exact enum values from Section 5/6/7 of the problem statement.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount_type(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("amount must be a number")
        return value


class AnalyzeTicketRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "ticket_id": "TKT-001",
                "complaint": "I sent 5000 taka to a wrong number around 2pm today.",
                "language": "en",
                "channel": "in_app_chat",
                "user_type": "customer",
                "campaign_context": "boishakh_bonanza_day_1",
                "transaction_history": [
                    {
                        "transaction_id": "TXN-9101",
                        "timestamp": "2026-04-14T14:08:22Z",
                        "type": "transfer",
                        "amount": 5000,
                        "counterparty": "+8801719876543",
                        "status": "completed",
                    }
                ],
                "metadata": {},
            }
        },
    )

    ticket_id: str = Field(
        ...,
        min_length=1,
        description="Unique ticket identifier. Echoed in the response.",
    )
    complaint: str = Field(
        ...,
        min_length=1,
        description="Customer complaint in English, Bangla, or Banglish.",
    )
    language: Optional[str] = Field(None, description="One of: en, bn, mixed.")
    channel: Optional[str] = Field(
        None, description="One of: in_app_chat, call_center, email, merchant_portal, field_agent."
    )
    user_type: Optional[str] = Field(
        None, description="One of: customer, merchant, agent, unknown."
    )
    campaign_context: Optional[str] = Field(None, description="Campaign identifier.")
    transaction_history: list[TransactionEntry] = Field(
        default_factory=list, description="Recent transactions (typically 2-5). May be empty."
    )
    metadata: Optional[dict[str, Any]] = Field(None, description="Additional simulated context.")

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ticket_id must not be blank")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError("ticket_id must not contain control characters")
        return value


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
