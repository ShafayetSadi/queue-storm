"""Deterministic routing: department, severity, and human_review_required.

Department is a fixed lookup from case_type (with a refund context override).
Severity and review follow the policy in architecture Sections 12, calibrated
against the public sample pack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.constants import DEPARTMENT_BY_CASE_TYPE
from app.engine.feature_extractor import ComplaintFeatures
from app.engine.matcher import MatchResult
from app.engine.normalizer import NormalizedRequest

_HIGH_AMOUNT_THRESHOLD = 5000.0

# Case types that warrant human review once a specific transaction is pinned.
_REVIEW_CASE_TYPES = {"wrong_transfer", "duplicate_payment", "agent_cash_in_issue"}

# Base severity by case type (before amount/phishing modifiers).
_BASE_SEVERITY = {
    "payment_failed": "high",
    "duplicate_payment": "high",
    "agent_cash_in_issue": "high",
    "merchant_settlement_delay": "medium",
    "refund_request": "low",
    "other": "low",
}


@dataclass
class Routing:
    department: str
    severity: str
    human_review_required: bool
    reasons: list[str]


def _amount_value(norm: NormalizedRequest, match: MatchResult) -> float:
    values = list(norm.amounts)
    if match.selected and match.selected.amount is not None:
        values.append(match.selected.amount)
    return max(values) if values else 0.0


def _department(case_type: str, verdict: str) -> str:
    if case_type == "refund_request" and verdict == "inconsistent":
        return "dispute_resolution"
    return DEPARTMENT_BY_CASE_TYPE.get(case_type, "customer_support")


def _severity(
    case_type: str, features: ComplaintFeatures, amount: float
) -> str:
    if case_type == "phishing_or_social_engineering" or features.credential_shared:
        return "critical"
    if case_type == "wrong_transfer":
        return "high" if amount >= _HIGH_AMOUNT_THRESHOLD else "medium"
    return _BASE_SEVERITY.get(case_type, "low")


def _human_review(
    case_type: str,
    verdict: str,
    match: MatchResult,
    features: ComplaintFeatures,
    amount: float,
) -> bool:
    if case_type == "phishing_or_social_engineering" or features.credential_shared:
        return True
    if verdict == "inconsistent":
        return True
    # Ambiguous / insufficient: ask for clarification first, no review yet.
    if match.relevant_transaction_id is None:
        return match.ambiguous and amount >= _HIGH_AMOUNT_THRESHOLD
    return case_type in _REVIEW_CASE_TYPES


def route_case(
    norm: NormalizedRequest,
    features: ComplaintFeatures,
    match: MatchResult,
    case_type: str,
    verdict: str,
) -> Routing:
    amount = _amount_value(norm, match)
    severity = _severity(case_type, features, amount)
    department = _department(case_type, verdict)
    review = _human_review(case_type, verdict, match, features, amount)

    reasons: list[str] = []
    if review:
        reasons.append("human_review_required")
    if amount >= _HIGH_AMOUNT_THRESHOLD:
        reasons.append("high_value")
    return Routing(department, severity, review, reasons)
