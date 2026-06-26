"""The LLM may enrich text, but must never be load-bearing for correctness or
safety: when it fails or returns invalid output, the deterministic baseline is
returned.
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


def test_llm_invalid_enum_is_rejected():
    bad = {
        "agent_summary": "summary",
        "recommended_next_action": "",
        "customer_reply": "we will help you",
    }
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=_FakeClient(bad))
    assert res.case_type == "wrong_transfer"
    assert "llm_fallback" in (res.reason_codes or [])


def test_llm_cannot_override_scored_fields():
    # Even a valid LLM response cannot change deterministic investigation results.
    payload = {
        "agent_summary": "LLM summary",
        "recommended_next_action": "Verify the transaction.",
        "customer_reply": "We have noted your concern.",
    }
    res = analyze_ticket(WRONG_TRANSFER, settings=LLM_ON, llm_client=_FakeClient(payload))
    assert res.relevant_transaction_id == "TXN-9101"
    assert res.case_type == "wrong_transfer"
    assert res.evidence_verdict == "consistent"
    assert res.severity == "high"
    assert res.human_review_required is True
    assert res.department == "dispute_resolution"
    assert res.agent_summary == "LLM summary"


def test_text_only_llm_payload_is_accepted():
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
    assert res.agent_summary == payload["agent_summary"]
    assert res.recommended_next_action == payload["recommended_next_action"]
    assert payload["customer_reply"] in res.customer_reply
    assert "do not share" in res.customer_reply.lower()
    assert res.confidence == 0.88
