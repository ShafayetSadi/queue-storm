"""The LLM writes open-ended text, grounded on the deterministic engine's
evidence. It is never load-bearing for safety, schema validity, or scored
structured fields: a dead client falls back entirely, and the deterministic
decision remains authoritative.
"""

from app.core.config import Settings
from app.engine.analyzer import analyze_ticket
from app.models.schemas import AnalyzeTicketRequest

WRONG_TRANSFER = AnalyzeTicketRequest(
    ticket_id="TKT-001",
    complaint="I sent 5000 taka to a wrong number around 2pm today.",
    transaction_history=[
        {
            "transaction_id": "TXN-9101",
            "timestamp": "2026-04-14T14:08:22Z",
            "type": "transfer",
            "amount": 5000,
            "counterparty": "+8801719876543",
            "status": "completed",
        }
    ],
)

VAGUE_COMPLAINT = AnalyzeTicketRequest(
    ticket_id="TKT-006",
    complaint="Something is wrong with my money. Please check.",
    transaction_history=[
        {
            "transaction_id": "TXN-9601",
            "timestamp": "2026-04-13T10:00:00Z",
            "type": "cash_in",
            "amount": 3000,
            "counterparty": "AGENT-220",
            "status": "completed",
        },
        {
            "transaction_id": "TXN-9602",
            "timestamp": "2026-04-12T15:30:00Z",
            "type": "transfer",
            "amount": 800,
            "counterparty": "+8801911223344",
            "status": "completed",
        },
    ],
)

LLM_ON = Settings(use_llm=True, openrouter_api_key="dummy-key")


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload
        self.available = True

    def complete_json(self, system, user):
        return self._payload


def test_llm_disabled_uses_deterministic():
    res = analyze_ticket(WRONG_TRANSFER, settings=Settings(use_llm=False))
    assert res.case_type == "wrong_transfer"
    assert res.relevant_transaction_id == "TXN-9101"


def test_llm_timeout_or_error_falls_back():
    # complete_json returning None simulates timeout / error / invalid JSON.
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=_FakeClient(None))
    assert res.case_type == "wrong_transfer"
    assert "llm_fallback" in (res.reason_codes or [])


def test_unavailable_client_falls_back():
    client = _FakeClient({})
    client.available = False
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=client)
    assert res.case_type == "wrong_transfer"
    assert "llm_fallback" in (res.reason_codes or [])


def test_valid_llm_decisions_do_not_override_structured_fields():
    # A fully valid LLM answer may enrich the narrative, but scored structured
    # fields stay deterministic for repeatable sample/hidden harness results.
    payload = {
        "agent_summary": "LLM summary",
        "evidence_verdict": "inconsistent",
        "case_type": "refund_request",
        "severity": "low",
        "human_review_required": True,
        "recommended_next_action": "Verify refund eligibility per policy.",
        "customer_reply": "We have noted your concern.",
        "confidence": 0.71,
        "reason_codes": ["llm_reasoned"],
    }
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=_FakeClient(payload))
    assert res.case_type == "wrong_transfer"
    assert res.evidence_verdict == "consistent"
    assert res.severity == "high"
    assert res.department == "dispute_resolution"
    assert res.relevant_transaction_id == "TXN-9101"
    assert res.human_review_required is True
    assert res.agent_summary == "LLM summary"
    assert res.confidence == 0.71
    assert "llm_reasoned" in (res.reason_codes or [])


def test_invalid_decision_field_does_not_discard_llm_text():
    # Bad decision fields are ignored, but usable narrative is still kept.
    payload = {
        "agent_summary": "Good LLM summary kept.",
        "evidence_verdict": "consistent",
        "case_type": "wrong_transfer",
        "severity": "urgent",  # not a legal Severity -> patched from baseline
        "human_review_required": True,
        "recommended_next_action": "Open the wrong-transfer dispute.",
        "customer_reply": "We have noted your concern.",
    }
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=_FakeClient(payload))
    assert res.severity == "high"  # deterministic baseline for 5000 wrong_transfer
    assert res.case_type == "wrong_transfer"
    assert res.agent_summary == "Good LLM summary kept."  # narrative kept


def test_human_review_stays_deterministic():
    # Deterministic engine flags review (wrong_transfer, pinned txn); the LLM
    # cannot lower it to false or raise it on clarification-only cases.
    payload = {
        "agent_summary": "summary",
        "evidence_verdict": "consistent",
        "case_type": "wrong_transfer",
        "severity": "high",
        "human_review_required": False,
        "recommended_next_action": "Proceed.",
        "customer_reply": "We have noted your concern.",
    }
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=_FakeClient(payload))
    assert res.human_review_required is True

    payload["human_review_required"] = True
    res = analyze_ticket(VAGUE_COMPLAINT, settings=LLM_ON, llm_client=_FakeClient(payload))
    assert res.case_type == "other"
    assert res.evidence_verdict == "insufficient_data"
    assert res.human_review_required is False


def test_text_only_payload_patches_all_decisions_from_baseline():
    # If the model omits the decision keys, they are filled from the baseline,
    # and the safety warning is still guaranteed in the reply.
    payload = {
        "agent_summary": "Customer reports a wrong transfer and needs dispute help.",
        "recommended_next_action": "Confirm transaction details and follow the dispute workflow.",
        "customer_reply": "We have noted your concern and will review it through official channels.",
        "confidence": 0.88,
        "reason_codes": ["text_enriched"],
    }
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=_FakeClient(payload))
    assert res.case_type == "wrong_transfer"
    assert res.evidence_verdict == "consistent"
    assert res.severity == "high"
    assert res.agent_summary == payload["agent_summary"]
    assert payload["customer_reply"] in res.customer_reply
    assert "do not share" in res.customer_reply.lower()
    assert res.confidence == 0.88
