"""Canonical enums, taxonomies, keyword maps, and reply templates.

Every enum value here is copied verbatim from the problem statement (Section 7 /
the sample pack `_meta.allowed_enums`). Variants (case, plurals, spelling) are
scored as schema violations, so these strings are the single source of truth.
"""

from __future__ import annotations

# --- Official output enums -------------------------------------------------

EVIDENCE_VERDICTS = ("consistent", "inconsistent", "insufficient_data")

CASE_TYPES = (
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "duplicate_payment",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "phishing_or_social_engineering",
    "other",
)

SEVERITIES = ("low", "medium", "high", "critical")

DEPARTMENTS = (
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "merchant_operations",
    "agent_operations",
    "fraud_risk",
)

# --- Official input enums (transaction history) ----------------------------

TRANSACTION_TYPES = (
    "transfer",
    "payment",
    "cash_in",
    "cash_out",
    "settlement",
    "refund",
)

TRANSACTION_STATUSES = ("completed", "failed", "pending", "reversed")

# --- Routing: department is a deterministic lookup from case_type -----------
# Section 7.2 / 12. refund_request is context-sensitive and handled in routing.

DEPARTMENT_BY_CASE_TYPE = {
    "wrong_transfer": "dispute_resolution",
    "payment_failed": "payments_ops",
    "refund_request": "customer_support",
    "duplicate_payment": "payments_ops",
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "phishing_or_social_engineering": "fraud_risk",
    "other": "customer_support",
}

# --- Keyword maps (English + Bangla + Banglish) ----------------------------
# Used by the deterministic classifier and safety pre-scan. Lowercased Latin
# keywords are matched against a normalized analysis copy; Bangla keywords are
# matched against the raw text (Bangla has no case).

WRONG_TRANSFER_KEYWORDS = (
    "wrong number", "wrong person", "wrong recipient", "wrong account",
    "mistaken", "by mistake", "typed wrong", "reverse it", "reverse the",
    "sent to the wrong", "wrongly sent", "sent wrong",
    "bhul number", "bhul manush", "vul number", "bhul kore", "vul kore",
    "bhul kore pathaisi", "vul kore pathaisi",
    "ভুল নম্বর", "ভুল নাম্বার", "ভুল নম্বরে", "ভুল নাম্বারে",
    "ভুল মানুষ", "ভুল একাউন্ট", "ভুল অ্যাকাউন্ট",
    "ভুলে পাঠিয়েছি", "ভুলে পাঠাইছি", "ভুল করে", "ভুলে সেন্ড", "ফেরত",
)

FAILED_PAYMENT_KEYWORDS = (
    "failed", "unsuccessful", "did not go through", "didn't go through",
    "transaction failed", "payment failed", "app showed failed",
    "payment hoy nai", "payment hoyni", "payment hoye nai",
    "balance was deducted", "balance deducted", "money was deducted",
    "deducted but", "deduct hoise", "deducted hoyeche",
    "fail hoise", "fail hoyeche", "taka kete", "taka kete gese",
    "টাকা কাটা", "টাকা কেটে গেছে", "টাকা কেটে গিয়েছে",
    "কেটে নিয়েছে", "কেটে নিয়েছে", "ব্যালেন্স কাটা", "ব্যর্থ", "ফেইল",
)

REFUND_KEYWORDS = (
    "refund", "return my money", "return the money", "money back",
    "want my money back", "changed my mind", "don't want", "do not want",
    "ferot chai", "taka ferot", "টাকা ফেরত", "রিফান্ড", "ফেরত চাই",
)

DUPLICATE_KEYWORDS = (
    "twice", "two times", "double", "duplicate", "charged again",
    "charged twice", "same payment twice", "deducted twice", "paid twice",
    "dui bar", "duibar", "duibar payment", "দুইবার",
    "দুই বার", "দুবার", "ডাবল", "দুইবার কাটা", "দুইবার পেমেন্ট", "দুই বার পেমেন্ট",
)

MERCHANT_SETTLEMENT_KEYWORDS = (
    "settlement", "settled", "not settled", "sales", "payout",
    "merchant account", "settle hoyni", "সেটেলমেন্ট", "সেটেল হয়নি",
)

AGENT_CASH_IN_KEYWORDS = (
    "cash in", "cash-in", "cashin", "agent", "deposit through",
    "balance not added", "didn't get balance", "did not reflect",
    "byalens", "ক্যাশ ইন", "এজেন্ট", "ব্যালেন্সে আসেনি", "ব্যালেন্সে আসে নাই",
)

PHISHING_KEYWORDS = (
    "otp", "pin", "password", "verification code", "security code",
    "called me", "someone called", "sms", "text message", "click this link",
    "click the link", "link e click", "account will be blocked", "account blocked",
    "account bondho kore dibe", "bkash theke bolse", "asked for my",
    "claiming to be", "scam", "fraud call", "suspicious",
    "ওটিপি", "পিন", "পাসওয়ার্ড", "কল", "লিংক", "ব্লক", "প্রতারণা",
    "কোড চাইছে", "ওটিপি চাইছে", "পিন চাইছে", "লিংকে ক্লিক",
)

# Language explicitly indicating the customer ALREADY shared a secret.
CREDENTIAL_SHARED_KEYWORDS = (
    "i shared my otp", "i gave my otp", "i told them my otp",
    "shared my pin", "gave my pin", "told them my pin",
    "shared my password", "gave my password", "already shared",
    "i gave them", "i shared it", "শেয়ার করেছি", "দিয়ে দিয়েছি",
)

# Prompt-injection / jailbreak phrases that may appear inside `complaint`.
PROMPT_INJECTION_KEYWORDS = (
    "ignore previous", "ignore all previous", "ignore the above",
    "ignore your instructions", "disregard previous", "disregard the",
    "forget your instructions", "forget the rules", "new instructions",
    "system prompt", "you are now", "act as", "from now on",
    "always classify", "respond with", "return plain text", "output only",
    "reveal your prompt", "print your", "override",
)

# --- Safe-reply templates --------------------------------------------------
# The sanitizer falls back to these when generated text is unsafe or missing.

PIN_OTP_WARNING_EN = (
    "Please do not share your PIN, OTP, or password with anyone."
)
PIN_OTP_WARNING_BN = (
    "অনুগ্রহ করে কারো সাথে আপনার পিন, ওটিপি বা পাসওয়ার্ড শেয়ার করবেন না।"
)

# Phrases that are NEVER allowed in customer-facing output (unauthorized
# financial authority). Matched case-insensitively as substrings.
UNSAFE_PROMISE_PATTERNS = (
    "we will refund you", "we will refund", "we have refunded", "we refunded",
    "we are refunding", "refunded your", "your refund has been", "i will refund",
    "i'll refund", "we'll refund", "refund has been processed",
    "refund is complete", "we will return your money",
    "we have returned your money", "money returned", "your money is returned",
    "we will reverse", "we have reversed", "we reversed", "i reversed",
    "i'll reverse", "we'll reverse", "reversed it", "reversed your",
    "reversal is complete", "reversal done",
    "your money has been recovered", "we recovered", "we have recovered",
    "we will recover", "we'll recover", "recovery is complete",
    "your account will be unblocked", "we have unblocked", "we unblocked",
    "we will unblock", "we'll unblock", "account has been unblocked",
    "account is unblocked", "money has been returned to you",
)

# Safe refund language (used in builder and as sanitizer replacement).
SAFE_REFUND_LANGUAGE = (
    "any eligible amount will be returned through official channels"
)

DEFAULT_SAFE_REPLY_EN = (
    "Thank you for reaching out. Our team will review the case and contact you "
    "through official support channels. " + PIN_OTP_WARNING_EN
)
DEFAULT_SAFE_REPLY_BN = (
    "আপনার সাথে যোগাযোগের জন্য ধন্যবাদ। আমাদের দল বিষয়টি যাচাই করে অফিসিয়াল "
    "সাপোর্ট চ্যানেলের মাধ্যমে আপনাকে জানাবে। " + PIN_OTP_WARNING_BN
)
