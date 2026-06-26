"""Deterministic case_type classification.

Rule-first and safety-aware: phishing and duplicate run before ordinary payment
classes (architecture Section 11). Classification uses both complaint language
AND the type of the selected/candidate transaction, so a transfer-not-received
complaint is still recognised as ``wrong_transfer`` even without explicit
"wrong" wording.
"""

from __future__ import annotations

from typing import Optional

from app.engine.feature_extractor import ComplaintFeatures
from app.engine.matcher import MatchResult
from app.engine.normalizer import NormalizedRequest

_NON_RECEIPT_HINTS = (
    "didn't get", "did not get", "didnt get", "didn't receive", "did not receive",
    "not received", "hasn't received", "haven't received", "never received",
    "did not arrive", "pai ni", "paini", "পাইনি", "পায়নি", "আসেনি", "আসে নাই",
)
_SEND_HINTS = (
    "i sent", "sent to", "transferred", "pathalam", "pathiyechi",
    "পাঠিয়েছি", "পাঠালাম", "টাকা পাঠ",
)


def _has(norm: NormalizedRequest, hints: tuple[str, ...]) -> bool:
    return any(h in norm.analysis_text or h in norm.complaint_original for h in hints)


def _dominant_type(match: MatchResult) -> Optional[str]:
    if match.selected and match.selected.type:
        return match.selected.type
    types = {t.type for t in match.candidates if t.type}
    return next(iter(types)) if len(types) == 1 else None


def classify_case(
    norm: NormalizedRequest, features: ComplaintFeatures, match: MatchResult
) -> tuple[str, list[str]]:
    dominant = _dominant_type(match)
    selected = match.selected
    reasons: list[str] = []

    # 1. Phishing / social engineering — safety class, highest priority.
    if features.phishing_language:
        reasons.append("phishing")
        if features.credential_shared:
            reasons.append("credential_shared")
        return "phishing_or_social_engineering", reasons

    # 2. Duplicate payment.
    if match.is_duplicate or (
        features.duplicate_language and dominant in {"payment", "transfer"}
    ):
        reasons.append("duplicate_payment")
        return "duplicate_payment", reasons

    # 3. Agent cash-in issue.
    if features.agent_cash_in_language or dominant == "cash_in":
        reasons.append("agent_cash_in")
        return "agent_cash_in_issue", reasons

    # 4. Merchant settlement delay.
    if features.merchant_settlement_language or dominant == "settlement":
        reasons.append("merchant_settlement")
        return "merchant_settlement_delay", reasons

    # 5. Failed payment (often with deducted balance).
    if features.failed_payment_language or (
        dominant == "payment" and selected is not None and selected.status == "failed"
    ):
        reasons.append("payment_failed")
        return "payment_failed", reasons

    # 6. Wrong transfer — explicit wording, or a transfer the recipient didn't get.
    transfer_problem = dominant == "transfer" and (
        _has(norm, _NON_RECEIPT_HINTS) or _has(norm, _SEND_HINTS)
    )
    if features.wrong_transfer_language or transfer_problem:
        reasons.append("wrong_transfer_claim")
        return "wrong_transfer", reasons

    # 7. Refund request.
    if features.refund_language:
        reasons.append("refund_request")
        return "refund_request", reasons

    # 8. Fallback.
    if features.vague_language or match.relevant_transaction_id is None:
        reasons.append("vague_complaint")
    return "other", reasons
