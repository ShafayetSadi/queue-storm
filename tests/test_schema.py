from app.core import constants


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
