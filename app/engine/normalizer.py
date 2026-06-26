"""Normalize a raw request into a canonical analysis representation.

Goal: make the deterministic engine robust to Bangla digits, varied amount and
phone formats, and free-form complaint text, while preserving the original text
for summaries and replies. Nothing here raises; bad input degrades to empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models.schemas import AnalyzeTicketRequest, TransactionEntry

# Bangla (Bengali) digit -> ASCII digit translation table.
_BANGLA_DIGITS = "০১২৩৪৫৬৭৮৯"
_BANGLA_TRANS = {ord(b): str(i) for i, b in enumerate(_BANGLA_DIGITS)}

# Transaction-id pattern, e.g. TXN-9101, TKT-001 (we only keep TXN-like here).
_TXN_ID_RE = re.compile(r"\bTXN[-_ ]?\d+\b", re.IGNORECASE)
# Merchant / agent / biller identifiers mentioned in free text.
_ENTITY_ID_RE = re.compile(r"\b(?:MERCHANT|AGENT|BILLER)[-_][A-Z0-9-]+\b", re.IGNORECASE)
# Phone numbers: optional +88, then 01XXXXXXXXX (BD mobile).
_PHONE_RE = re.compile(r"(?:\+?88)?0?1\d{9}\b")
# Explicit clock mentions such as "2pm", "2 PM", "14:08", or "at 9".
_TIME_RE = re.compile(
    r"\b(?:around|at|about|প্রায়|সময়|সময়)?\s*"
    r"([01]?\d|2[0-3])(?::[0-5]\d)?\s*(am|pm)?\b",
    re.IGNORECASE,
)
# Amount mentions: "5000 taka", "৳5,000", "5k", "1200tk".
_AMOUNT_RE = re.compile(
    r"(?:৳|tk|taka|bdt|৳\s*)?\s*([\d,]+(?:\.\d+)?)\s*(k\b|taka|tk|৳|bdt|টাকা)?",
    re.IGNORECASE,
)


@dataclass
class NormalizedTransaction:
    raw: TransactionEntry
    transaction_id: Optional[str]
    timestamp: Optional[datetime]
    type: Optional[str]
    amount: Optional[float]
    counterparty: Optional[str]
    counterparty_digits: str  # digits-only form for phone matching
    status: Optional[str]


@dataclass
class NormalizedRequest:
    request: AnalyzeTicketRequest
    complaint_original: str
    analysis_text: str  # lowercased, Bangla digits -> ASCII, whitespace collapsed
    mentioned_transaction_ids: list[str] = field(default_factory=list)
    amounts: list[float] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)  # digits-only, last 10
    entity_ids: list[str] = field(default_factory=list)
    mentioned_hours: list[int] = field(default_factory=list)
    transactions: list[NormalizedTransaction] = field(default_factory=list)

    @property
    def has_history(self) -> bool:
        return len(self.transactions) > 0


def bangla_to_ascii_digits(text: str) -> str:
    return text.translate(_BANGLA_TRANS)


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _phone_key(value: str) -> str:
    """Normalize a phone-ish string to its last 10 digits for comparison."""
    digits = _digits_only(value)
    return digits[-10:] if len(digits) >= 10 else digits


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _extract_amounts(analysis_text: str) -> list[float]:
    amounts: list[float] = []
    for match in _AMOUNT_RE.finditer(analysis_text):
        number_str, suffix = match.group(1), (match.group(2) or "").lower()
        before = analysis_text[max(0, match.start() - 1):match.start()]
        after = analysis_text[match.end():match.end() + 3]
        if before == ":" or after.startswith(":"):
            continue
        cleaned = number_str.replace(",", "")
        if not cleaned or cleaned == ".":
            continue
        try:
            value = float(cleaned)
        except ValueError:
            continue
        if suffix == "k":
            value *= 1000
        if not suffix and after.strip().startswith(("am", "pm")):
            continue
        # Ignore bare phone-like numbers and tiny bare numbers that are likely
        # times, counts, or dates. Currency-suffixed small amounts still count.
        if not suffix and value > 1_000_000:
            continue
        if not suffix and value <= 24:
            continue
        if value <= 0:
            continue
        amounts.append(value)
    # De-duplicate while preserving order.
    seen: set[float] = set()
    unique: list[float] = []
    for amount in amounts:
        if amount not in seen:
            seen.add(amount)
            unique.append(amount)
    return unique


def _extract_hours(analysis_text: str) -> list[int]:
    hours: list[int] = []
    for match in _TIME_RE.finditer(analysis_text):
        raw_hour, meridiem = match.group(1), (match.group(2) or "").lower()
        try:
            hour = int(raw_hour)
        except ValueError:
            continue
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            hours.append(hour)
    return list(dict.fromkeys(hours))


def normalize_transaction(entry: TransactionEntry) -> NormalizedTransaction:
    counterparty = entry.counterparty or ""
    return NormalizedTransaction(
        raw=entry,
        transaction_id=entry.transaction_id,
        timestamp=_parse_timestamp(entry.timestamp),
        type=(entry.type or "").strip().lower() or None,
        amount=float(entry.amount) if entry.amount is not None else None,
        counterparty=entry.counterparty,
        counterparty_digits=_phone_key(counterparty),
        status=(entry.status or "").strip().lower() or None,
    )


def normalize_request(request: AnalyzeTicketRequest) -> NormalizedRequest:
    complaint = request.complaint or ""
    ascii_complaint = bangla_to_ascii_digits(complaint)
    analysis_text = re.sub(r"\s+", " ", ascii_complaint).strip().lower()

    mentioned_ids = [m.group(0).upper().replace("_", "-").replace(" ", "-")
                     for m in _TXN_ID_RE.finditer(ascii_complaint)]
    entity_ids = [m.group(0).upper() for m in _ENTITY_ID_RE.finditer(ascii_complaint)]
    phones = []
    for m in _PHONE_RE.finditer(ascii_complaint):
        key = _phone_key(m.group(0))
        if key:
            phones.append(key)

    transactions = [normalize_transaction(t) for t in request.transaction_history]

    return NormalizedRequest(
        request=request,
        complaint_original=complaint,
        analysis_text=analysis_text,
        mentioned_transaction_ids=list(dict.fromkeys(mentioned_ids)),
        amounts=_extract_amounts(analysis_text),
        phones=list(dict.fromkeys(phones)),
        entity_ids=list(dict.fromkeys(entity_ids)),
        mentioned_hours=_extract_hours(analysis_text),
        transactions=transactions,
    )


def phone_key(value: str) -> str:
    """Public helper so the matcher can compare counterparties consistently."""
    return _phone_key(value)
