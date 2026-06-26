"""Deterministic transaction selection.

Picks ``relevant_transaction_id`` from the supplied history, or ``None`` when the
evidence is absent or genuinely ambiguous. This id is authoritative for the
response regardless of the LLM, so the logic is conservative: when in doubt,
return ``None`` rather than guessing (the spec rewards "insufficient_data" over
a wrong dispute).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.engine.feature_extractor import ComplaintFeatures
from app.engine.normalizer import NormalizedRequest, NormalizedTransaction, phone_key

_AMOUNT_TOL = 0.5
_DUPLICATE_WINDOW_SECONDS = 600  # 10 minutes


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
            # Multiple equally-plausible matches -> do not guess.
            return MatchResult(
                None, None, candidates, ambiguous=True, reason="ambiguous_amount"
            )

        # Amount mentioned but nothing matched: fall through to weaker signals.

    # 3. Counterparty (phone) match when no amount disambiguation was possible.
    phone_hits = _phone_matches(norm)
    if len(phone_hits) == 1:
        t = phone_hits[0]
        return MatchResult(t.transaction_id, t, phone_hits, reason="counterparty_match")
    if len(phone_hits) >= 2:
        return MatchResult(None, None, phone_hits, ambiguous=True,
                           reason="ambiguous_counterparty")

    # 4. Single-transaction history with a concrete (non-vague) complaint:
    #    safe to treat that lone transaction as the subject.
    if len(txns) == 1 and not features.vague_language and features.any_payment_intent:
        t = txns[0]
        return MatchResult(t.transaction_id, t, [t], reason="sole_transaction")

    # 5. Nothing reliable to select.
    return MatchResult(None, None, list(txns), reason="no_reliable_match")
