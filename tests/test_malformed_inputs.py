def test_invalid_json_returns_400(client):
    resp = client.post(
        "/analyze-ticket", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_missing_required_fields_returns_400(client):
    resp = client.post("/analyze-ticket", json={"complaint": "hello"})
    assert resp.status_code == 400


def test_empty_complaint_returns_422(client):
    resp = client.post("/analyze-ticket", json={"ticket_id": "T", "complaint": "   "})
    assert resp.status_code == 422


def test_missing_transaction_history_is_ok(client):
    resp = client.post(
        "/analyze-ticket", json={"ticket_id": "T", "complaint": "Something is wrong with my money."}
    )
    assert resp.status_code == 200
    assert resp.json()["relevant_transaction_id"] is None


def test_malformed_transaction_entry_does_not_crash(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "T",
            "complaint": "I sent 5000 to a wrong number",
            "transaction_history": [{"transaction_id": "TXN-1", "amount": "not-a-number"}],
        },
    )
    # Bad amount type is ignored; service still responds (200) or rejects (400),
    # but never crashes.
    assert resp.status_code in (200, 400)


def test_boolean_transaction_amount_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-001",
            "complaint": "I sent 5000 taka to a wrong number around 2pm today.",
            "transaction_history": [{"amount": False}],
        },
    )
    assert resp.status_code == 400


def test_does_not_leak_internal_details_on_error(client):
    resp = client.post("/analyze-ticket", json={"complaint": "x"})
    body = resp.json()
    assert "Traceback" not in str(body)
    assert "openrouter" not in str(body).lower()
