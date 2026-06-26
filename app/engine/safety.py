"""Always-on safety layer.

Two responsibilities, both deterministic and final regardless of the LLM:

1. ``prescan`` — flag credential-share, phishing, and prompt-injection signals
   before classification.
2. ``sanitize`` — scrub the final ``customer_reply`` / ``recommended_next_action``
   of any credential request, unauthorized refund/reversal promise, or
   third-party redirect; guarantee the PIN/OTP warning; and *escalate only*
   (never de-escalate) severity / human_review for safety-critical cases.

The sanitizer may only make a response safer. It can replace unsafe text with a
known-safe template and raise severity, but it never lowers severity or clears
``human_review_required``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core import constants
from app.engine.feature_extractor import ComplaintFeatures
from app.engine.normalizer import NormalizedRequest

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_BANGLA_RE = re.compile(r"[ঀ-৿]")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

# A request for a secret credential: a request verb followed (within a few
# words) by a credential noun. Negated mentions ("never ask for your PIN",
# "do not share your OTP") are allowed and excluded below.
_CRED_NOUN = r"(?:pin|otp|password|card\s*number|full\s*card|cvv|secret\s*credential)"
_CRED_REQUEST_RE = re.compile(
    r"(?:ask(?:ing)?(?:\s+\w+){0,3}\s+for|share|send|provide|give|enter|submit"
    r"|type|tell\s+\w+|need|reveal|verify\s+with)\s+(?:your|their|the|me|us\s+your)?\s*"
    + _CRED_NOUN,
    re.IGNORECASE,
)
_NEGATIONS = ("never", "do not", "don't", "dont", "won't", "wont", "not ", "without")
# Bangla negated credential mention (e.g. "পিন ... শেয়ার করবেন না").
_CRED_NOUN_BN_RE = re.compile(r"(পিন|ওটিপি|পাসওয়ার্ড)")
_THIRD_PARTY_PATTERNS = (
    "call this number", "call the number", "contact this number",
    "whatsapp", "telegram", "click this link", "click the link",
    "dial this", "message this number",
)
_SAFE_PRESENCE_HINTS = (
    "do not share", "never ask", "never share", "without sharing",
    "শেয়ার করবেন না", "শেয়ার করবে না",
)


@dataclass
class SafetyContext:
    phishing: bool
    credential_shared: bool
    prompt_injection: bool
    bangla: bool


def prescan(norm: NormalizedRequest, features: ComplaintFeatures) -> SafetyContext:
    bangla = (norm.request.language or "").strip().lower() == "bn" or bool(
        _BANGLA_RE.search(norm.complaint_original)
    )
    return SafetyContext(
        phishing=features.phishing_language,
        credential_shared=features.credential_shared,
        prompt_injection=features.prompt_injection_language,
        bangla=bangla,
    )


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(p in low for p in patterns)


def _requests_credential(text: str) -> bool:
    """True if the text asks for a secret credential. Negated safety reminders
    ("we never ask for your PIN", "do not share your OTP") are NOT flagged."""
    low = text.lower()
    for m in _CRED_REQUEST_RE.finditer(low):
        preceding = low[max(0, m.start() - 14): m.start()]
        if not any(neg in preceding for neg in _NEGATIONS):
            return True
    return False


def _safe_reply(bangla: bool) -> str:
    return constants.DEFAULT_SAFE_REPLY_BN if bangla else constants.DEFAULT_SAFE_REPLY_EN


def _ensure_warning(reply: str, bangla: bool) -> str:
    if _contains_any(reply, _SAFE_PRESENCE_HINTS):
        return reply
    warn = constants.PIN_OTP_WARNING_BN if bangla else constants.PIN_OTP_WARNING_EN
    return f"{reply.rstrip()} {warn}"


def _add_reason(response: dict, code: str) -> None:
    codes = response.get("reason_codes")
    if not isinstance(codes, list):
        codes = []
    if code not in codes:
        codes.append(code)
    response["reason_codes"] = codes


def sanitize(response: dict, ctx: SafetyContext) -> dict:
    """Scrub the response in place and return it. Safe to call on any response
    dict (LLM-produced or deterministic)."""
    bangla = ctx.bangla
    unsafe_template_used = False

    reply = str(response.get("customer_reply") or "")
    action = str(response.get("recommended_next_action") or "")

    # 1. Credential requests anywhere -> replace the offending field entirely.
    if _requests_credential(reply):
        reply = _safe_reply(bangla)
        unsafe_template_used = True
    if _requests_credential(action):
        action = (
            "Escalate to the fraud_risk team and never request the customer's "
            "PIN, OTP, password, or card number."
        )
        unsafe_template_used = True

    # 2. Unauthorized refund/reversal/unblock promises -> safe eligibility wording.
    if _contains_any(reply, constants.UNSAFE_PROMISE_PATTERNS):
        reply = _safe_reply(bangla)
        unsafe_template_used = True
    if _contains_any(action, constants.UNSAFE_PROMISE_PATTERNS):
        action = (
            "Verify eligibility through official policy; "
            + constants.SAFE_REFUND_LANGUAGE + "."
        )
        unsafe_template_used = True

    # 3. Third-party redirects / external links -> safe template.
    if _URL_RE.search(reply) or _contains_any(reply, _THIRD_PARTY_PATTERNS):
        reply = _safe_reply(bangla)
        unsafe_template_used = True
    if _URL_RE.search(action) or _contains_any(action, _THIRD_PARTY_PATTERNS):
        action = (
            "Direct the customer only to official support channels; do not refer "
            "them to any third-party contact."
        )
        unsafe_template_used = True

    # 4. Guarantee the credential-safety warning is present in the reply.
    reply = _ensure_warning(reply, bangla)

    response["customer_reply"] = reply
    response["recommended_next_action"] = action or (
        "Review the case and follow up through official support channels."
    )

    # 5. Reason codes for transparency.
    if unsafe_template_used:
        _add_reason(response, "safe_template_applied")
    if ctx.prompt_injection:
        _add_reason(response, "prompt_injection_ignored")
    if ctx.credential_shared:
        _add_reason(response, "credential_protection")

    # 6. Escalate-only: never make the response less safe.
    if ctx.phishing or ctx.credential_shared:
        if _SEVERITY_RANK.get(response.get("severity"), 0) < _SEVERITY_RANK["critical"]:
            response["severity"] = "critical"
        response["human_review_required"] = True

    return response
