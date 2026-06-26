"""Deterministic transaction selection.

Picks ``relevant_transaction_id`` from the supplied history, or ``None`` when the
evidence is absent or genuinely ambiguous. This id is authoritative for the
response regardless of the LLM, so the logic is conservative: when in doubt,
return ``None`` rather than guessing (the spec rewards "insufficient_data" over
a wrong dispute).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from app.engine.feature_extractor import ComplaintFeatures
from app.engine.normalizer import NormalizedRequest, NormalizedTransaction, phone_key

_AMOUNT_TOL = 0.5
_DUPLICATE_WINDOW_SECONDS = 600  # 10 minutes
_TIME_MATCH_WINDOW = timedelta(hours=1)


@dataclass
class MatchResult:
    relevant_transaction_id: Optional[str]
    selected: Optional[NormalizedTransaction]
    candidates: list[NormalizedTransaction] = field(default_factory=list)
    ambiguous: bool = False
    is_duplicate: bool = False
    duplicate_partner_id: Optional[str] = None
    reason: str = ""


def _complaint_amount(norm: NormalizedRequest) -> Optional[float]:
    return norm.amounts[0] if norm.amounts else None


def _amount_matches(norm: NormalizedRequest, amount: float) -> list[NormalizedTransaction]:
    return [
        t for t in norm.transactions
        if t.amount is not None and abs(t.amount - amount) <= _AMOUNT_TOL
    ]


def _ts_key(t: NormalizedTransaction) -> float:
    return t.timestamp.timestamp() if t.timestamp else 0.0


def _latest(transactions: list[NormalizedTransaction]) -> NormalizedTransaction:
    return max(transactions, key=_ts_key)


def _find_duplicate_group(
    candidates: list[NormalizedTransaction], features: ComplaintFeatures
) -> Optional[list[NormalizedTransaction]]:
    """A duplicate group: >=2 completed txns with same amount, counterparty and
    type, that are either close in time or backed by explicit duplicate wording.
    """
    by_key: dict[tuple, list[NormalizedTransaction]] = {}
    for t in candidates:
        if t.status not in (None, "completed"):
            continue
        key = (t.amount, (t.counterparty or "").upper(), t.type)
        by_key.setdefault(key, []).append(t)

    for group in by_key.values():
        if len(group) < 2:
            continue
        times = sorted(_ts_key(t) for t in group if t.timestamp)
        close = len(times) >= 2 and (times[-1] - times[0]) <= _DUPLICATE_WINDOW_SECONDS
        if features.duplicate_language or close:
            return group
    return None


def _phone_matches(norm: NormalizedRequest) -> list[NormalizedTransaction]:
    if not norm.phones:
        return []
    targets = set(norm.phones)
    return [t for t in norm.transactions if t.counterparty_digits and
            phone_key(t.counterparty_digits) in targets]


def _expected_types(features: ComplaintFeatures) -> set[str]:
    types: set[str] = set()
    if features.wrong_transfer_language:
        types.add("transfer")
    if features.failed_payment_language or features.refund_language:
        types.add("payment")
    if features.duplicate_language:
        types.update({"payment", "transfer"})
    if features.merchant_settlement_language:
        types.add("settlement")
    if features.agent_cash_in_language:
        types.add("cash_in")
    return types


def _type_narrow(
    candidates: list[NormalizedTransaction], features: ComplaintFeatures
) -> list[NormalizedTransaction]:
    expected = _expected_types(features)
    if not expected:
        return candidates
    narrowed = [t for t in candidates if t.type in expected]
    return narrowed or candidates


def _time_narrow(
    candidates: list[NormalizedTransaction], norm: NormalizedRequest
) -> list[NormalizedTransaction]:
    if not norm.mentioned_hours:
        return candidates
    narrowed: list[NormalizedTransaction] = []
    for t in candidates:
        if not t.timestamp:
            continue
        for hour in norm.mentioned_hours:
            target = t.timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
            if abs(t.timestamp - target) <= _TIME_MATCH_WINDOW:
                narrowed.append(t)
                break
    return narrowed or candidates


def select_transaction(
    norm: NormalizedRequest, features: ComplaintFeatures
) -> MatchResult:
    txns = norm.transactions
    if not txns:
        return MatchResult(None, None, reason="no_history")

    # 1. Explicit transaction id mentioned in the complaint wins outright.
    for tid in norm.mentioned_transaction_ids:
        for t in txns:
            if t.transaction_id and t.transaction_id.upper() == tid.upper():
                return MatchResult(t.transaction_id, t, [t], reason="id_match")

    amount = _complaint_amount(norm)

    # 2. Amount-driven selection (the strongest signal in the sample pack).
    if amount is not None:
        candidates = _amount_matches(norm, amount)

        if len(candidates) == 1:
            t = candidates[0]
            return MatchResult(t.transaction_id, t, candidates, reason="amount_match")

        if len(candidates) >= 2:
            dup = _find_duplicate_group(candidates, features)
            if dup:
                chosen = _latest(dup)
                partner = next(
                    (t.transaction_id for t in dup if t is not chosen), None
                )
                return MatchResult(
                    chosen.transaction_id, chosen, dup, is_duplicate=True,
                    duplicate_partner_id=partner, reason="duplicate_pair",
                )
            # Narrow by phone if the complaint named a counterparty.
            phone_narrowed = [t for t in candidates if t in _phone_matches(norm)]
            if len(phone_narrowed) == 1:
                t = phone_narrowed[0]
                return MatchResult(
                    t.transaction_id, t, candidates, reason="amount_phone_match"
                )
            candidates = phone_narrowed or candidates

            type_narrowed = _type_narrow(candidates, features)
            if len(type_narrowed) == 1:
                t = type_narrowed[0]
                return MatchResult(
                    t.transaction_id, t, candidates, reason="amount_type_match"
                )
            candidates = type_narrowed

            time_narrowed = _time_narrow(candidates, norm)
            if len(time_narrowed) == 1:
                t = time_narrowed[0]
                return MatchResult(
                    t.transaction_id, t, candidates, reason="amount_time_match"
                )
            # Multiple equally-plausible matches -> do not guess.
            return MatchResult(
                None, None, candidates, ambiguous=True, reason="ambiguous_amount"
            )

        # Amount mentioned but nothing matched: fall through to weaker signals.

    # 3. Counterparty (phone) match when no amount disambiguation was possible.
    phone_hits = _phone_matches(norm)
    phone_hits = _time_narrow(_type_narrow(phone_hits, features), norm)
    if len(phone_hits) == 1:
        t = phone_hits[0]
        return MatchResult(t.transaction_id, t, phone_hits, reason="counterparty_match")
    if len(phone_hits) >= 2:
        return MatchResult(None, None, phone_hits, ambiguous=True,
                           reason="ambiguous_counterparty")

    # 4. A concrete complaint with an explicit time can identify the only
    # nearby transaction even when the customer omits amount/counterparty.
    time_hits = _time_narrow(_type_narrow(txns, features), norm)
    if norm.mentioned_hours and len(time_hits) == 1 and features.any_payment_intent:
        t = time_hits[0]
        return MatchResult(t.transaction_id, t, time_hits, reason="time_match")
    if norm.mentioned_hours and 1 < len(time_hits) < len(txns):
        return MatchResult(None, None, time_hits, ambiguous=True,
                           reason="ambiguous_time")

    # 5. Single-transaction history with a concrete (non-vague) complaint:
    #    safe to treat that lone transaction as the subject.
    if len(txns) == 1 and not features.vague_language and features.any_payment_intent:
        t = txns[0]
        return MatchResult(t.transaction_id, t, [t], reason="sole_transaction")

    # 6. Nothing reliable to select.
    return MatchResult(None, None, list(txns), reason="no_reliable_match")
