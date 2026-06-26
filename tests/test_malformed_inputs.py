def test_invalid_json_returns_400(client):
    resp = client.post(
        "/analyze-ticket", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_missing_required_fields_returns_400(client):
    resp = client.post("/analyze-ticket", json={"complaint": "hello"})
    assert resp.status_code == 400


def test_empty_ticket_id_returns_400(client):
    resp = client.post("/analyze-ticket", json={"ticket_id": "", "complaint": "hello"})
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


def test_valid_optional_request_enums_are_accepted(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-ENUM",
            "complaint": "I sent 5000 taka to a wrong number.",
            "language": "mixed",
            "channel": "in_app_chat",
            "user_type": "customer",
            "transaction_history": [
                {
                    "transaction_id": "TXN-1",
                    "timestamp": "2026-04-14T14:08:22Z",
                    "type": "transfer",
                    "amount": 5000,
                    "counterparty": "+8801719876543",
                    "status": "completed",
                }
            ],
        },
    )
    assert resp.status_code == 200


def test_invalid_language_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-ENUM",
            "complaint": "I sent 5000 taka to a wrong number.",
            "language": "english",
        },
    )
    assert resp.status_code == 400


def test_invalid_channel_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-ENUM",
            "complaint": "I sent 5000 taka to a wrong number.",
            "channel": "sms",
        },
    )
    assert resp.status_code == 400


def test_invalid_user_type_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-ENUM",
            "complaint": "I sent 5000 taka to a wrong number.",
            "user_type": "admin",
        },
    )
    assert resp.status_code == 400


def test_invalid_metadata_shape_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-META",
            "complaint": "I sent 5000 taka to a wrong number.",
            "metadata": [],
        },
    )
    assert resp.status_code == 400


def test_invalid_transaction_type_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-TYPE",
            "complaint": "I sent 5000 taka to a wrong number.",
            "transaction_history": [
                {
                    "transaction_id": "TXN-1",
                    "timestamp": "2026-04-14T14:08:22Z",
                    "type": "send_money",
                    "amount": 5000,
                    "counterparty": "+8801719876543",
                    "status": "completed",
                }
            ],
        },
    )
    assert resp.status_code == 400


def test_invalid_transaction_status_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-STATUS",
            "complaint": "I sent 5000 taka to a wrong number.",
            "transaction_history": [
                {
                    "transaction_id": "TXN-1",
                    "timestamp": "2026-04-14T14:08:22Z",
                    "type": "transfer",
                    "amount": 5000,
                    "counterparty": "+8801719876543",
                    "status": "done",
                }
            ],
        },
    )
    assert resp.status_code == 400


def test_invalid_transaction_timestamp_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-TIME",
            "complaint": "I sent 5000 taka to a wrong number.",
            "transaction_history": [
                {
                    "transaction_id": "TXN-1",
                    "timestamp": "not-a-time",
                    "type": "transfer",
                    "amount": 5000,
                    "counterparty": "+8801719876543",
                    "status": "completed",
                }
            ],
        },
    )
    assert resp.status_code == 400


def test_non_string_transaction_id_returns_400(client):
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-ID",
            "complaint": "I sent 5000 taka to a wrong number.",
            "transaction_history": [
                {
                    "transaction_id": 123,
                    "timestamp": "2026-04-14T14:08:22Z",
                    "type": "transfer",
                    "amount": 5000,
                    "counterparty": "+8801719876543",
                    "status": "completed",
                }
            ],
        },
    )
    assert resp.status_code == 400


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
