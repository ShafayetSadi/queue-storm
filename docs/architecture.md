# QueueStorm Investigator Architecture

Current-state architecture for the SUST CSE Carnival 2026 Codex Community
Hackathon preliminary submission.

QueueStorm Investigator is a single FastAPI service for digital-finance support
ticket analysis. It exposes the two judged endpoints, `GET /health` and
`POST /analyze-ticket`, and is currently hosted at:

```text
https://queue-storm-qbfrm.ondigitalocean.app/
```

The service is intentionally a modular monolith: no database, no queue, no GPU,
no local model artifact, and no required network dependency for correctness.
OpenRouter can be enabled for text enrichment, but the deterministic engine is
the authority for scored decisions.

## Submission Surface

| Artifact | Current status |
|---|---|
| Live URL | `https://queue-storm-qbfrm.ondigitalocean.app/` |
| Health endpoint | `GET /health` returns `{"status":"ok"}` |
| Analysis endpoint | `POST /analyze-ticket` returns the official response schema |
| Dependency file | `pyproject.toml` with locked dependencies in `uv.lock` |
| Container files | `Dockerfile`, `docker-compose.yml` |
| Redeploy runbook | `RUNBOOK.md` |
| Public sample outputs | `samples/sample_outputs.json` |
| Public sample source | `docs/SUST_Preli_Sample_Cases.json` |

## Runtime Flow

```text
POST /analyze-ticket
    |
    v
Pydantic request validation
    |
    v
normalize complaint + transaction history
    |
    v
extract complaint features
    |
    v
safety prescan
    |
    v
deterministic transaction matcher
    |
    v
deterministic baseline response
    |   - case_type
    |   - evidence_verdict
    |   - severity
    |   - department
    |   - human_review_required
    |   - baseline text / confidence / reason_codes
    |
    +--> optional single OpenRouter call
    |       - keeps scored fields deterministic
    |       - enriches narrative text, confidence, and reason_codes
    |       - falls back on missing key, timeout, invalid JSON, or provider error
    |
    v
always-on safety sanitizer
    |
    v
final response schema validation
    |
    v
safe JSON response
```

The deterministic baseline is always computed first. That baseline gives the
service a complete, valid, judgeable result even when `USE_LLM=false`, no
OpenRouter key is present, the provider times out, or model output is malformed.

## Field Ownership

The public and hidden harnesses score structured fields as single-answer values,
so those fields must not vary by model judgment.

| Field | Owner | Reason |
|---|---|---|
| `ticket_id` | Request echo | Must preserve caller identity. |
| `relevant_transaction_id` | Deterministic matcher | Must be grounded in supplied history only. |
| `case_type` | Deterministic classifier | Keeps sample and hidden runs repeatable. |
| `evidence_verdict` | Deterministic verdict engine | Encodes evidence support or contradiction. |
| `severity` | Deterministic router | Calibrated to safety and amount policy. |
| `department` | Deterministic lookup | Derived from `case_type` and verdict. |
| `human_review_required` | Deterministic router / sanitizer | Prevents model de-escalation. |
| `agent_summary` | Baseline template, optionally LLM-enriched | Open-ended text. |
| `recommended_next_action` | Baseline template, optionally LLM-enriched | Open-ended text, sanitized last. |
| `customer_reply` | Baseline template, optionally LLM-enriched | Open-ended text, sanitized last. |
| `confidence` | Baseline or validated LLM value | Must remain `0..1`. |
| `reason_codes` | Baseline plus validated LLM additions | Deduplicated audit trail. |

`app/engine/analyzer.py` enforces this split. `_merge_llm()` only copies
`agent_summary`, `recommended_next_action`, `customer_reply`, `confidence`, and
`reason_codes` from the LLM result. It then derives `department` again from the
deterministic decision.

## API Contract

### `GET /health`

Returns exactly:

```json
{"status":"ok"}
```

This endpoint does not call OpenRouter or any external service.

### `POST /analyze-ticket`

The request requires `ticket_id` and `complaint`. Optional context fields are
validated strictly when present:

- `language`: `en`, `bn`, `mixed`
- `channel`: `in_app_chat`, `call_center`, `email`, `merchant_portal`,
  `field_agent`
- `user_type`: `customer`, `merchant`, `agent`, `unknown`
- `transaction_history`: list of synthetic transaction objects
- `metadata`: optional object

The response follows the official output schema:

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT via TXN-9101 to what they now believe was the wrong recipient.",
  "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the wrong-transfer dispute workflow per policy.",
  "customer_reply": "We have noted your concern about transaction TXN-9101. Please do not share your PIN, OTP, or password with anyone. Our dispute team will review the case and contact you through official support channels.",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["wrong_transfer_claim", "evidence_consistent", "human_review_required", "high_value"]
}
```

Error responses are controlled JSON bodies:

| Status | Meaning |
|---|---|
| `200` | Valid request analyzed successfully. |
| `400` | Invalid JSON, missing required fields, invalid enum, or malformed typed field. |
| `422` | Complaint parses but is semantically empty. |
| `500` | Controlled internal failure, without stack traces or secrets. |

## Modules

```text
app/
  main.py                    FastAPI app, route registration, exception handlers
  api/routes.py              /health and /analyze-ticket
  models/schemas.py          Request/response models and official enums
  core/config.py             Environment-backed settings
  core/constants.py          Routing constants and keyword groups
  core/logging.py            Safe structured log helper
  engine/analyzer.py         End-to-end orchestration
  engine/normalizer.py       Text/history normalization
  engine/feature_extractor.py Complaint signal extraction
  engine/matcher.py          Relevant transaction selection
  engine/classifier.py       Deterministic case_type classification
  engine/verdict.py          Deterministic evidence_verdict
  engine/routing.py          Department, severity, human review
  engine/response_builder.py Baseline summaries, replies, confidence, reasons
  engine/safety.py           Prescan and final sanitizer
  llm/client.py              OpenRouter-compatible HTTP client
  llm/investigator.py        Single-call LLM text enrichment
```

## Deterministic Investigation

### Normalization

`app/engine/normalizer.py` builds a canonical analysis view while preserving the
original complaint text for replies. It handles:

- whitespace cleanup and lowercase analysis text
- Bangla digit conversion
- BDT amount extraction, including comma-formatted and Bangla amounts
- phone/counterparty normalization
- transaction ID extraction
- approximate hour extraction such as `2pm`
- ISO timestamp parsing
- missing `transaction_history` as an empty list

### Feature Extraction

`app/engine/feature_extractor.py` derives boolean signals for:

- wrong transfer
- failed payment
- refund request
- duplicate payment
- merchant settlement delay
- agent cash-in issue
- phishing or social engineering
- credential shared
- prompt injection
- vague complaint

These features are intentionally simple and auditable because the scoring logic
depends on predictable evidence handling.

### Transaction Matching

`app/engine/matcher.py` chooses `relevant_transaction_id` conservatively:

1. Exact transaction ID mention wins if it exists in history.
2. Amount match is the strongest general signal.
3. Duplicate groups are detected by same amount, counterparty, type, and close
   timestamps, with the later transaction selected as the suspected duplicate.
4. Phone/counterparty, transaction type, and time hints narrow candidates.
5. A single concrete transaction can be selected for a concrete, non-vague
   complaint.
6. Ambiguous or weak evidence returns `null` instead of guessing.

Ambiguity is deliberate: the rubric rewards `insufficient_data` over a wrong
transaction guess.

### Classification

`app/engine/classifier.py` prioritizes safety and high-signal classes:

1. `phishing_or_social_engineering`
2. `duplicate_payment`
3. `agent_cash_in_issue`
4. `merchant_settlement_delay`
5. `payment_failed`
6. `wrong_transfer`
7. `refund_request`
8. `other`

Classification uses complaint language plus the selected/candidate transaction
type, so a transfer non-receipt complaint can still become `wrong_transfer`
without exact "wrong number" wording.

### Evidence Verdict

`app/engine/verdict.py` answers whether the supplied history supports the
complaint:

| Verdict | Current policy |
|---|---|
| `consistent` | Selected history supports or makes the complaint plausible. |
| `inconsistent` | A selected transaction exists but status, type, prior-recipient pattern, or reversal/refund state contradicts the complaint. |
| `insufficient_data` | No reliable transaction, ambiguous candidates, empty history for a transaction claim, or vague complaint. |

Examples handled by current tests include completed payment contradicting a
failed-payment claim, duplicate claim with only one payment, completed
settlement contradicting a settlement-delay claim, and wrong transfer to an
established recipient.

### Routing

`app/engine/routing.py` determines department, severity, and review:

| Case type | Department |
|---|---|
| `wrong_transfer` | `dispute_resolution` |
| `payment_failed` | `payments_ops` |
| `refund_request` | `customer_support`, or `dispute_resolution` if inconsistent |
| `duplicate_payment` | `payments_ops` |
| `merchant_settlement_delay` | `merchant_operations` |
| `agent_cash_in_issue` | `agent_operations` |
| `phishing_or_social_engineering` | `fraud_risk` |
| `other` | `customer_support` |

Severity is `critical` for phishing or shared credentials, `high` for duplicate
payment / agent cash-in / failed payment and high-value wrong transfers,
`medium` for ordinary wrong transfers and merchant settlement delay, and `low`
for low-risk refund or vague support cases.

Human review is required for phishing, credential sharing, inconsistent
evidence, selected wrong-transfer disputes, selected duplicate payments, and
selected agent cash-in issues. Ambiguous high-value matches also require review.

## LLM Integration

The LLM integration is optional and uses OpenRouter through an OpenAI-compatible
HTTP client.

```env
USE_LLM=true
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=google/gemini-2.5-flash-lite
LLM_TIMEOUT_SECONDS=10
LLM_MAX_RETRIES=0
```

The model is called once per ticket when `USE_LLM=true` and
`OPENROUTER_API_KEY` is present. It receives:

- untrusted complaint text
- normalized transaction history
- deterministic matcher result
- deterministic suggested decision fields
- deterministic reason codes

`app/llm/investigator.py` validates the model response per field. Invalid enum
values, invalid booleans, empty text, bad confidence, invalid JSON, provider
errors, or timeouts all fall back to deterministic values. The model may improve
wording, but it cannot invent transaction IDs, choose departments, bypass
safety, or make live financial promises.

## Safety Model

Safety is enforced before and after generation:

1. `safety.prescan()` detects phishing, credential sharing, prompt injection,
   and safety-sensitive complaint text.
2. `safety.sanitize()` checks the final response after optional LLM enrichment.

The sanitizer blocks:

- asking for PIN, OTP, password, CVV, security code, or full card details
- unauthorized refund, reversal, recovery, or account-unblock promises
- third-party redirects, external links, non-official channels, and
  merchant-direct contact instructions
- prompt-injection attempts embedded in the complaint

The sanitizer may raise severity to `critical`, force
`human_review_required=true`, replace unsafe text with known-safe templates, and
append reason codes such as `safe_template_applied` or
`prompt_injection_ignored`. It never lowers severity or clears human review.

## Testing and Validation

Current test coverage includes:

```text
tests/test_health.py
tests/test_schema.py
tests/test_sample_cases.py
tests/test_safety.py
tests/test_malformed_inputs.py
tests/test_evidence_reasoning_hidden.py
tests/test_llm_fallback.py
tests/k6/health_p95.js
tests/k6/analyze_ticket_p95.js
```

Main validation commands:

```bash
uv run pytest -q
uv run python scripts/run_sample_cases.py --base-url http://localhost:8000
BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh
```

Hosted sample verification:

```bash
curl -fsS https://queue-storm-qbfrm.ondigitalocean.app/health
uv run python scripts/run_sample_cases.py --base-url https://queue-storm-qbfrm.ondigitalocean.app
```

The public sample harness compares the core structured fields:
`relevant_transaction_id`, `evidence_verdict`, `case_type`, `department`,
`severity`, and `human_review_required`.

## Deployment

The runtime image is built from `python:3.12-slim` and uses `uv` for dependency
sync. It runs as a non-root user, exposes port `8000`, includes a container
health check, and starts Uvicorn with two workers:

```text
uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 2
```

The service reads `PORT` from the environment and has no required startup
dependency outside the local process. With no OpenRouter key, it still returns
fully valid deterministic analyses.

## Known Limitations

- The service investigates only the transaction history included in the request.
  It does not query any real ledger.
- It is a support-agent copilot, not a financial authority. It never confirms a
  refund, reversal, recovery, or account unblock.
- Deterministic Bangla/Banglish handling is keyword and normalization based.
  The optional LLM improves same-language wording when enabled.
- The preliminary-round design intentionally avoids user accounts, dashboards,
  persistence, queues, and multi-service orchestration because they do not
  improve the judged API surface.

## Design Rationale

The architecture is optimized for the rubric:

- Evidence reasoning is deterministic, auditable, and conservative.
- Safety policy is deterministic and always runs last.
- The schema is locked by Pydantic models and final validation.
- The service remains judgeable without secrets or external providers.
- Optional LLM usage is limited to text enrichment, which improves manual
  readability without risking scored-field drift.
