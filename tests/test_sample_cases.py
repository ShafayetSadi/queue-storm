"""The deterministic engine must be functionally equivalent to the public
expected_output on the core decision fields, plus severity and review."""

CORE_FIELDS = ["relevant_transaction_id", "evidence_verdict", "case_type", "department"]


def test_core_fields_match_expected(client, sample_cases):
    for case in sample_cases:
        resp = client.post("/analyze-ticket", json=case["input"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        exp = case["expected_output"]
        for field in CORE_FIELDS:
            assert body[field] == exp[field], (
                f"{case['id']} {field}: got {body[field]!r} expected {exp[field]!r}"
            )
        assert body["severity"] == exp["severity"], case["id"]
        assert body["human_review_required"] == exp["human_review_required"], case["id"]
