"""Deterministic evidence_verdict.

Answers: does the supplied transaction history support the complaint?
- consistent: history supports / makes the complaint plausible.
- inconsistent: a relevant transaction exists but the pattern or status
  contradicts the complaint (e.g. an "established recipient" wrong-transfer).
- insufficient_data: no relevant transaction, ambiguous match, empty history
  for a transaction claim, or a vague complaint.
"""

from __future__ import annotations

from app.engine.feature_extractor import ComplaintFeatures
from app.engine.matcher import MatchResult
from app.engine.normalizer import NormalizedRequest


def _same_counterparty_count(norm: NormalizedRequest, counterparty: str) -> int:
    target = (counterparty or "").upper()
    if not target:
        return 0
    return sum(
        1 for t in norm.transactions
        if (t.counterparty or "").upper() == target
    )


def decide_verdict(
    norm: NormalizedRequest,
    features: ComplaintFeatures,
    match: MatchResult,
    case_type: str,
) -> tuple[str, list[str]]:
    # No reliable transaction to reason about.
    if match.relevant_transaction_id is None or match.selected is None:
        reasons = ["ambiguous_match"] if match.ambiguous else ["needs_clarification"]
        return "insufficient_data", reasons

    selected = match.selected

    # Wrong transfer to an established recipient contradicts the "wrong" claim.
    if case_type == "wrong_transfer":
        if _same_counterparty_count(norm, selected.counterparty or "") >= 2:
            return "inconsistent", [
                "established_recipient_pattern", "evidence_inconsistent"
            ]

    # Duplicate claim but only a single matching payment exists.
    if case_type == "duplicate_payment" and not match.is_duplicate:
        return "inconsistent", ["single_payment_only", "evidence_inconsistent"]

    # Refund of an already-reversed transaction contradicts the request.
    if case_type == "refund_request" and selected.status == "reversed":
        return "inconsistent", ["already_reversed", "evidence_inconsistent"]

    # Otherwise the history supports the complaint.
    return "consistent", ["evidence_consistent"]
