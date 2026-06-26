"""Build the free-text fields for the deterministic path.

Template-driven, evidence-aware, and safe by construction (no refund promises,
no credential requests; the safety sanitizer still runs afterwards as a backstop).
Replies are produced in Bangla when the input is Bangla.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core import constants
from app.engine.feature_extractor import ComplaintFeatures
from app.engine.matcher import MatchResult
from app.engine.normalizer import NormalizedRequest
from app.engine.routing import Routing

_BANGLA_RE = re.compile(r"[ঀ-৿]")

_CONFIDENCE_BY_REASON = {
    "id_match": 0.95,
    "amount_match": 0.9,
    "amount_phone_match": 0.9,
    "counterparty_match": 0.85,
    "duplicate_pair": 0.93,
    "sole_transaction": 0.82,
}


@dataclass
class BuiltText:
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    confidence: float
    reason_codes: list[str]


def _is_bangla(norm: NormalizedRequest) -> bool:
    if (norm.request.language or "").strip().lower() == "bn":
        return True
    return bool(_BANGLA_RE.search(norm.complaint_original))


def _amount_str(norm: NormalizedRequest, match: MatchResult) -> str:
    if match.selected and match.selected.amount is not None:
        return f"{int(match.selected.amount)}"
    if norm.amounts:
        return f"{int(norm.amounts[0])}"
    return "the reported amount"


def _confidence(match: MatchResult, verdict: str, case_type: str) -> float:
    if case_type == "phishing_or_social_engineering":
        return 0.95
    if match.ambiguous:
        return 0.65
    if match.relevant_transaction_id is None:
        return 0.6
    base = _CONFIDENCE_BY_REASON.get(match.reason, 0.8)
    if verdict == "inconsistent":
        base = min(base, 0.78)
    return round(base, 2)


def _warning(bangla: bool) -> str:
    return constants.PIN_OTP_WARNING_BN if bangla else constants.PIN_OTP_WARNING_EN


def build_text(
    norm: NormalizedRequest,
    features: ComplaintFeatures,
    match: MatchResult,
    case_type: str,
    verdict: str,
    routing: Routing,
    base_reason_codes: list[str],
) -> BuiltText:
    bangla = _is_bangla(norm)
    warn = _warning(bangla)
    tid = match.relevant_transaction_id
    amount = _amount_str(norm, match)
    safe_refund = constants.SAFE_REFUND_LANGUAGE

    summary, action, reply = _templates(
        norm, features, match, case_type, verdict, tid, amount, safe_refund, bangla, warn
    )

    confidence = _confidence(match, verdict, case_type)
    reason_codes = list(dict.fromkeys(base_reason_codes + routing.reasons))
    return BuiltText(summary, action, reply, confidence, reason_codes)


def _templates(norm, features, match, case_type, verdict, tid, amount,
               safe_refund, bangla, warn):  # noqa: ANN001 - internal helper
    # --- Phishing -----------------------------------------------------------
    if case_type == "phishing_or_social_engineering":
        summary = (
            "Customer reports a suspicious call/message asking for credentials "
            "(possible social engineering). "
            + ("Customer states they already shared a secret."
               if features.credential_shared
               else "Customer has not shared any credentials yet.")
        )
        action = (
            "Escalate to the fraud_risk team. Confirm to the customer that the "
            "company never asks for PIN, OTP, or password, and log the reported "
            "contact for fraud pattern analysis."
        )
        reply = (
            "Thank you for reaching out before sharing any information. We never "
            "ask for your PIN, OTP, or password under any circumstances. Please do "
            "not share these with anyone, even if they claim to be from us. Our "
            "fraud team has been notified of this incident."
        )
        return summary, action, reply

    # --- Insufficient / ambiguous ------------------------------------------
    if match.relevant_transaction_id is None:
        if match.ambiguous:
            summary = (
                f"Customer reports an issue involving {amount} BDT, but multiple "
                "transactions plausibly match and the correct one cannot be "
                "determined without more detail."
            )
            action = (
                "Reply to the customer asking for a disambiguating detail (e.g. "
                "the recipient's number) to identify the correct transaction. Do "
                "not initiate any dispute until the transaction is confirmed."
            )
            if bangla:
                reply = (
                    "যোগাযোগের জন্য ধন্যবাদ। একই পরিমাণের একাধিক লেনদেন দেখা যাচ্ছে। "
                    "সঠিক লেনদেনটি শনাক্ত করতে অনুগ্রহ করে প্রাপকের নম্বরটি জানান। " + warn
                )
            else:
                reply = (
                    "Thank you for reaching out. We see multiple transactions of a "
                    "similar amount. Could you share the recipient's number so we "
                    "can identify the right transaction? " + warn
                )
            return summary, action, reply
        # vague
        summary = (
            "Customer reports a vague concern without specifying a transaction, "
            "amount, or issue. Insufficient detail to identify any transaction."
        )
        action = (
            "Reply to the customer asking for specifics: which transaction, what "
            "amount, what went wrong, and the approximate time."
        )
        if bangla:
            reply = (
                "যোগাযোগের জন্য ধন্যবাদ। দ্রুত সাহায্যের জন্য অনুগ্রহ করে লেনদেন আইডি, "
                "পরিমাণ এবং কী সমস্যা হয়েছে তা জানান। " + warn
            )
        else:
            reply = (
                "Thank you for reaching out. To help you faster, please share the "
                "transaction ID, the amount involved, and a short description of "
                "what went wrong. " + warn
            )
        return summary, action, reply

    # --- Cases with an identified transaction ------------------------------
    if case_type == "wrong_transfer":
        if verdict == "inconsistent":
            summary = (
                f"Customer claims {tid} ({amount} BDT) was a wrong transfer, but "
                "history shows prior transfers to the same recipient, suggesting an "
                "established relationship."
            )
            action = (
                f"Flag for human review. Verify with the customer whether {tid} was "
                "genuinely a wrong transfer given the established pattern with this "
                "recipient."
            )
        else:
            summary = (
                f"Customer reports sending {amount} BDT via {tid} to what they now "
                "believe was the wrong recipient."
            )
            action = (
                f"Verify {tid} details with the customer and initiate the "
                "wrong-transfer dispute workflow per policy."
            )
        reply = (
            f"We have noted your concern about transaction {tid}. {warn} Our dispute "
            "team will review the case and contact you through official support "
            "channels."
        )
        return summary, action, reply

    if case_type == "payment_failed":
        summary = (
            f"Customer attempted a {amount} BDT payment ({tid}) which failed but "
            "reports the balance was deducted. Requires payments operations review."
        )
        action = (
            f"Investigate {tid} ledger status. If the balance was deducted on a "
            "failed payment, initiate the standard reversal flow within SLA."
        )
        reply = (
            f"We have noted that transaction {tid} may have caused an unexpected "
            f"balance deduction. Our payments team will review the case and "
            f"{safe_refund}. {warn}"
        )
        return summary, action, reply

    if case_type == "duplicate_payment":
        summary = (
            f"Customer reports a duplicate payment of {amount} BDT. Two matching "
            f"payments were found; {tid} is likely the duplicate."
        )
        action = (
            f"Verify the duplicate with payments_ops. If the biller confirms only "
            f"one payment was received, initiate reversal of {tid}."
        )
        reply = (
            f"We have noted the possible duplicate payment for transaction {tid}. "
            f"Our payments team will verify with the biller and {safe_refund}. {warn}"
        )
        return summary, action, reply

    if case_type == "agent_cash_in_issue":
        summary = (
            f"Customer reports a {amount} BDT agent cash-in ({tid}) not reflected in "
            "their balance."
        )
        action = (
            f"Investigate {tid} status with agent operations. Confirm the settlement "
            "state and resolve within the standard cash-in SLA."
        )
        if bangla:
            reply = (
                f"আপনার লেনদেন {tid} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স "
                f"দল এটি দ্রুত যাচাই করবে এবং অফিসিয়াল চ্যানেলে আপনাকে জানাবে। {warn}"
            )
        else:
            reply = (
                f"We have noted your concern about transaction {tid}. Our agent "
                f"operations team will review it and update you through official "
                f"support channels. {warn}"
            )
        return summary, action, reply

    if case_type == "merchant_settlement_delay":
        summary = (
            f"Merchant reports a {amount} BDT settlement ({tid}) delayed beyond the "
            "expected window. Settlement status is pending."
        )
        action = (
            f"Route to merchant_operations to verify the settlement batch status for "
            f"{tid}. If delayed, communicate a revised ETA to the merchant."
        )
        reply = (
            f"We have noted your concern about settlement {tid}. Our merchant "
            "operations team will check the batch status and update you on the "
            "expected settlement time through official channels."
        )
        return summary, action, reply

    if case_type == "refund_request":
        summary = (
            f"Customer requests a refund of {amount} BDT for {tid}. This is a refund "
            "request rather than a service failure."
        )
        action = (
            "Inform the customer that refund eligibility depends on the merchant's "
            "policy. Guide any next steps through official support channels."
        )
        reply = (
            "Thank you for reaching out. Refunds for completed merchant payments "
            "depend on policy verification. Our support team can guide the next "
            f"steps through official channels, and {safe_refund}. {warn}"
        )
        return summary, action, reply

    # --- Fallback (other with a transaction) -------------------------------
    summary = (
        f"Customer reports an issue related to transaction {tid} involving "
        f"{amount} BDT."
    )
    action = (
        f"Review {tid} and follow up with the customer through official channels "
        "to confirm the issue."
    )
    if bangla:
        reply = (
            f"আপনার লেনদেন {tid} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের দল বিষয়টি যাচাই "
            f"করে অফিসিয়াল চ্যানেলে আপনাকে জানাবে। {warn}"
        )
    else:
        reply = (
            f"We have noted your concern about transaction {tid}. Our team will "
            f"review the case and contact you through official support channels. "
            f"{warn}"
        )
    return summary, action, reply
