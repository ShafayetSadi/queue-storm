from app.core import constants
from app.models.schemas import AnalyzeTicketResponse

import pytest
from pydantic import ValidationError


REQUIRED_FIELDS = [
    "ticket_id", "relevant_transaction_id", "evidence_verdict", "case_type",
    "severity", "department", "agent_summary", "recommended_next_action",
    "customer_reply", "human_review_required",
]


def _analyze(client, payload):
    resp = client.post("/analyze-ticket", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_required_fields_present_and_typed(client, sample_cases):
    body = _analyze(client, sample_cases[0]["input"])
    for field in REQUIRED_FIELDS:
        assert field in body, f"missing {field}"
    assert isinstance(body["ticket_id"], str)
    assert isinstance(body["human_review_required"], bool)
    assert body["relevant_transaction_id"] is None or isinstance(
        body["relevant_transaction_id"], str
    )
    assert isinstance(body["agent_summary"], str) and body["agent_summary"].strip()
    assert (
        isinstance(body["recommended_next_action"], str)
        and body["recommended_next_action"].strip()
    )
    assert isinstance(body["customer_reply"], str) and body["customer_reply"].strip()
    if body.get("confidence") is not None:
        assert 0 <= body["confidence"] <= 1
    if body.get("reason_codes") is not None:
        assert isinstance(body["reason_codes"], list)
        assert all(isinstance(code, str) and code.strip() for code in body["reason_codes"])


def test_enums_are_exact(client, sample_cases):
    for case in sample_cases:
        body = _analyze(client, case["input"])
        assert body["evidence_verdict"] in constants.EVIDENCE_VERDICTS
        assert body["case_type"] in constants.CASE_TYPES
        assert body["severity"] in constants.SEVERITIES
        assert body["department"] in constants.DEPARTMENTS


def test_ticket_id_is_echoed(client, sample_cases):
    for case in sample_cases:
        body = _analyze(client, case["input"])
        assert body["ticket_id"] == case["input"]["ticket_id"]


def test_relevant_transaction_id_exists_in_history(client, sample_cases):
    for case in sample_cases:
        body = _analyze(client, case["input"])
        rtid = body["relevant_transaction_id"]
        if rtid is not None:
            ids = {t["transaction_id"] for t in case["input"].get("transaction_history", [])}
            assert rtid in ids, f"{case['id']}: {rtid} not in history"


def _valid_response_payload() -> dict:
    return {
        "ticket_id": "TKT-001",
        "relevant_transaction_id": "TXN-9101",
        "evidence_verdict": "consistent",
        "case_type": "wrong_transfer",
        "severity": "high",
        "department": "dispute_resolution",
        "agent_summary": "Customer reports a wrong transfer.",
        "recommended_next_action": "Verify the transaction and follow policy.",
        "customer_reply": "We have noted your concern.",
        "human_review_required": True,
        "confidence": 0.9,
        "reason_codes": ["wrong_transfer", "transaction_match"],
    }


@pytest.mark.parametrize("confidence", [-0.1, 1.1, "high"])
def test_response_confidence_must_be_number_between_zero_and_one(confidence):
    payload = _valid_response_payload()
    payload["confidence"] = confidence

    with pytest.raises(ValidationError):
        AnalyzeTicketResponse(**payload)


@pytest.mark.parametrize("field", ["ticket_id", "agent_summary", "recommended_next_action", "customer_reply"])
def test_required_response_strings_must_be_non_empty(field):
    payload = _valid_response_payload()
    payload[field] = "   "

    with pytest.raises(ValidationError):
        AnalyzeTicketResponse(**payload)


def test_response_reason_codes_must_be_non_empty_strings():
    payload = _valid_response_payload()
    payload["reason_codes"] = ["valid_code", ""]

    with pytest.raises(ValidationError):
        AnalyzeTicketResponse(**payload)
