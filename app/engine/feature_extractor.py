"""Extract boolean intent/safety features from a normalized complaint.

Latin keywords are matched against the lowercased ``analysis_text``; Bangla
keywords are matched against the original complaint (Bangla is caseless and the
analysis copy is lowercased, which is a no-op for Bangla but harmless).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core import constants
from app.engine.normalizer import NormalizedRequest


def _matches_any(norm: NormalizedRequest, keywords: tuple[str, ...]) -> bool:
    haystacks = (norm.analysis_text, norm.complaint_original)
    return any(kw in hay for kw in keywords for hay in haystacks if kw)


@dataclass
class ComplaintFeatures:
    wrong_transfer_language: bool
    failed_payment_language: bool
    refund_language: bool
    duplicate_language: bool
    merchant_settlement_language: bool
    agent_cash_in_language: bool
    phishing_language: bool
    credential_shared: bool
    prompt_injection_language: bool
    vague_language: bool
    is_merchant: bool

    @property
    def any_payment_intent(self) -> bool:
        return any(
            (
                self.wrong_transfer_language,
                self.failed_payment_language,
                self.refund_language,
                self.duplicate_language,
                self.merchant_settlement_language,
                self.agent_cash_in_language,
            )
        )


# A complaint is "vague" when it is short and carries no concrete signal.
_VAGUE_HINTS = (
    "something is wrong", "something wrong", "check my", "please check",
    "problem with my", "issue with my money", "kichu ekta", "টাকার সমস্যা",
)


def extract_complaint_features(norm: NormalizedRequest) -> ComplaintFeatures:
    user_type = (norm.request.user_type or "").strip().lower()

    phishing = _matches_any(norm, constants.PHISHING_KEYWORDS)
    credential_shared = _matches_any(norm, constants.CREDENTIAL_SHARED_KEYWORDS)

    has_concrete_signal = bool(
        norm.mentioned_transaction_ids or norm.amounts or norm.phones or norm.entity_ids
    )
    vague = (
        not has_concrete_signal
        and len(norm.analysis_text) <= 80
        and (
            _matches_any(norm, _VAGUE_HINTS)
            or len(norm.analysis_text.split()) <= 8
        )
    )

    return ComplaintFeatures(
        wrong_transfer_language=_matches_any(norm, constants.WRONG_TRANSFER_KEYWORDS),
        failed_payment_language=_matches_any(norm, constants.FAILED_PAYMENT_KEYWORDS),
        refund_language=_matches_any(norm, constants.REFUND_KEYWORDS),
        duplicate_language=_matches_any(norm, constants.DUPLICATE_KEYWORDS),
        merchant_settlement_language=_matches_any(
            norm, constants.MERCHANT_SETTLEMENT_KEYWORDS
        ),
        agent_cash_in_language=_matches_any(norm, constants.AGENT_CASH_IN_KEYWORDS),
        phishing_language=phishing,
        credential_shared=credential_shared,
        prompt_injection_language=_matches_any(
            norm, constants.PROMPT_INJECTION_KEYWORDS
        ),
        vague_language=vague,
        is_merchant=(user_type == "merchant"),
    )
