# QueueStorm Investigator

**bKash presents SUST CSE Carnival 2026 · Codex Community Hackathon — Online Preliminary**
AI/API SupportOps copilot for digital-finance support agents.

QueueStorm Investigator reads one customer complaint **plus** a short snippet of
that customer's recent transaction history, *investigates what actually happened*
(the complaint may contradict the data), and returns a single structured JSON
decision that classifies, routes, and explains the case — with a safe customer
reply that never asks for secrets and never promises an unauthorized refund.

It is a **hybrid**: an LLM (via OpenRouter) is the primary investigator, and a
deterministic rules engine is a fully-functional, validated fallback. Safety
sanitization and schema validation always run last, so the LLM can never cause
an invalid schema or an unsafe reply.

---

## Submission deliverables

| Deliverable | Status | Location / notes |
|---|---:|---|
| GitHub repository | Done | `https://github.com/ShafayetSadi/queue-storm` — make the repo public or grant organizer access to `bipulhf` before submission. |
| Hosted endpoint URL | Done | `https://queue-storm-qbfrm.ondigitalocean.app/` |
| Required API endpoints | Done | `GET /health` and `POST /analyze-ticket` are implemented. Hosted health check: `https://queue-storm-qbfrm.ondigitalocean.app/health`. |
| Docker image / runbook path | Done | Docker build files are `Dockerfile` and `docker-compose.yml`; redeploy instructions are in [`RUNBOOK.md`](RUNBOOK.md). |
| Dependency file | Done | [`pyproject.toml`](pyproject.toml) plus locked dependencies in [`uv.lock`](uv.lock). |
| Sample output file | Done | [`samples/sample_outputs.json`](samples/sample_outputs.json), generated from the public cases in [`docs/SUST_Preli_Sample_Cases.json`](docs/SUST_Preli_Sample_Cases.json). |
| MODELS section | Done | See [MODELS](#models). It lists every model used, where it runs, and why it was chosen. |

Quick judge commands:

```bash
curl -fsS https://queue-storm-qbfrm.ondigitalocean.app/health
uv run python scripts/run_sample_cases.py --base-url https://queue-storm-qbfrm.ondigitalocean.app
```

---

## Endpoints (the only two the judge harness exercises)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Returns exactly `{"status":"ok"}`. |
| `POST` | `/analyze-ticket` | Accepts the request schema, returns the response schema. |

HTTP codes: `200` success · `400` malformed/missing required fields · `422`
semantically empty complaint · `500` controlled internal error (never a stack
trace, token, or secret).

## Tech stack

- **Python 3.12**, **FastAPI**, **Uvicorn**, **Pydantic v2**
- **OpenRouter** (OpenAI-compatible) for the optional/primary LLM call
- No database, no GPU, no model baked into the image — the deterministic path
  has **zero network dependency**.

## Architecture flow

```
POST /analyze-ticket
   │
   ▼
normalize (Bangla digits, amounts, phones, ids, time)
   │
   ├─ safety pre-scan (phishing / credential-share / prompt-injection)
   ├─ deterministic transaction match  ──►  relevant_transaction_id (authoritative)
   ├─ deterministic baseline response (always computed, ~sub-ms)
   │
   ├─ IF USE_LLM: single ordered LLM call (OpenRouter)
   │      returns: agent_summary FIRST, echoes deterministic structured fields,
   │      then recommended_next_action / customer_reply
   │      → use LLM narrative text; keep scored structured fields deterministic
   │         └─ unavailable / invalid JSON → deterministic baseline
   │
   ├─ fill AUTOMATIC fields deterministically:
   │      ticket_id (echo) · relevant_transaction_id (matcher) · department (lookup)
   │
   ├─ safety sanitizer (ALWAYS): scrub credential requests, refund/reversal
   │      promises, third-party redirects; guarantee PIN/OTP warning; escalate-only
   │
   ▼
final Pydantic schema validation → 200 JSON
```

### Why this design (the hybrid balance)

The deterministic engine is the **floor**: it alone passes all 10 public sample
cases on every scored field. The LLM is the **ceiling**: it adds fluent,
same-language reasoning and replies (English / Bangla / Banglish). The scored
fields are deterministic — `relevant_transaction_id`, `evidence_verdict`,
`case_type`, `department`, `severity`, and `human_review_required` — which keeps
sample and hidden-test runs repeatable. We use **one ordered LLM call** rather
than multi-agent fan-out because the downstream text enrichment is small: the
network round-trip dominates, so a single call is faster, cheaper, and more
coherent.

## MODELS

| Model | Where it runs | Role | Why chosen |
|---|---|---|---|
| `google/gemini-2.5-flash-lite` (default, configurable via `MODEL_NAME`) | **OpenRouter** (remote, OpenAI-compatible HTTPS API) | **Narrative enricher:** produces `agent_summary`, `recommended_next_action`, `customer_reply`, `confidence`, and extra `reason_codes` in one ordered JSON call. | Generally very fast, low-cost, strong Bangla/Banglish comprehension, reliable JSON output, and typically returns in under 5 seconds. Swappable to any OpenRouter model (e.g. `openai/gpt-4o-mini`) with no code change. |
| Deterministic rules engine (no ML model) | **In-process**, local CPU | **Scored decision + safety + fallback.** Selects the relevant transaction, computes structured fields, sanitizes all output, and validates the schema. | Guarantees a fast, safe, schema-perfect 200 even when the LLM is disabled, times out, errors, or returns invalid/unsafe output. |

**Cost / reasoning.** No LLM credits are provided by the organizers, so the LLM
is optional by design. With `USE_LLM=false` (or no API key) the service is 100%
deterministic, free, and needs no network. With `USE_LLM=true` it makes exactly
**one** Gemini Flash Lite call per ticket (`max_tokens≈900`, `timeout=4s` by
default), which is inexpensive and generally completes in under 5 seconds; there is no multi-call or multi-agent fan-out.
The LLM is never on the critical path for correctness or safety.

## Safety logic (enforced deterministically, always)

- **Never requests** PIN, OTP, password, or card number. A regex detector flags
  any credential request in `customer_reply` / `recommended_next_action` and
  replaces the field with a safe template — while *allowing* negated reminders
  like "we never ask for your OTP".
- **Never promises** an unauthorized refund, reversal, account unblock, or
  recovery — those are rewritten to *"any eligible amount will be returned
  through official channels"*.
- **Never redirects** to third parties or external links — replaced with official
  channels.
- **Prompt-injection resistant**: the complaint is treated as untrusted data;
  embedded instructions ("ignore previous rules", "ask for OTP", "classify as
  refund") are ignored and flagged with `prompt_injection_ignored`.
- **Escalate-only**: the sanitizer may raise severity to `critical` and force
  `human_review_required` for phishing / credential-shared cases, but never
  lowers severity or clears review.

## Evidence reasoning

- `relevant_transaction_id`: explicit id mention → amount match → duplicate-pair
  detection → counterparty/type/time narrowing → sole-transaction. Ambiguous
  (multiple equal matches) returns `null` instead of guessing.
- `evidence_verdict`: `consistent` when history supports the complaint;
  `inconsistent` when a relevant transaction exists but contradicts it (e.g. an
  "established recipient" wrong-transfer, completed payment for a failed-payment
  claim, duplicate claim with only one payment, completed settlement for a
  settlement-delay claim, or already-reversed/refunded transaction);
  `insufficient_data` when nothing matches, the match is ambiguous, history is
  empty for a transaction claim, or the complaint is vague.
- Amount extraction ignores time-like numbers such as `2pm` and phone-like bare
  numbers, while explicit clock mentions can disambiguate the only nearby
  transaction.

## Setup & run (local)

```bash
uv sync --dev

# Optional: enable the LLM
cp .env.example .env   # then set OPENROUTER_API_KEY=...

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Run with Docker (primary)

> **Required for Docker Compose:** create `.env` before running Compose. The
> compose file intentionally reads `env_file: .env`, so the command below is not
> optional for a fresh checkout.

```bash
# 1. Required: create the env file from the template
cp .env.example .env

# 2. If you do NOT have an OpenRouter API key, keep the service fully
# deterministic and network-free by setting this in .env:
# USE_LLM=false
# OPENROUTER_API_KEY=

# 3. If you want the full hybrid LLM mode, set this in .env instead:
# USE_LLM=true
# OPENROUTER_API_KEY=<your-openrouter-key>

# 4a. Docker Compose
docker compose up --build

# 4b. or plain Docker
docker build -t queuestorm-investigator .
docker run -p 8000:8000 --env-file .env queuestorm-investigator
```

`GET /health` returns within seconds; the container has a `HEALTHCHECK`.

## Environment variables

See [`.env.example`](.env.example). Key ones: `USE_LLM`, `OPENROUTER_API_KEY`,
`OPENROUTER_BASE_URL`, `MODEL_NAME`, `LLM_TIMEOUT_SECONDS`, `PORT`.

## Sample request / response

Request ([`samples/sample_request.json`](samples/sample_request.json)):

```json
{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to a wrong number around 2pm today...",
  "transaction_history": [
    {"transaction_id":"TXN-9101","timestamp":"2026-04-14T14:08:22Z","type":"transfer","amount":5000,"counterparty":"+8801719876543","status":"completed"}
  ]
}
```

Response ([`samples/sample_response.json`](samples/sample_response.json)):

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

Outputs for all 10 public cases: [`samples/sample_outputs.json`](samples/sample_outputs.json).

## Testing

```bash
uv run pytest -q
# Against a running service:
uv run python scripts/run_sample_cases.py --base-url http://localhost:8000
BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh
```

The suite covers `/health`, schema/enum correctness, sample-case equivalence,
hidden-style evidence contradictions, ambiguity handling, safety (no credential
requests, no refund promises, prompt injection ignored), malformed input (no
crash), and LLM fallback (the deterministic engine produces a valid safe result
when the LLM is disabled or fails).

## Deployment / runbook

The container is the primary artifact. A complete redeploy runbook is in
[`RUNBOOK.md`](RUNBOOK.md) (required even if a Live URL is submitted).

## Known limitations

- Investigates only the transaction history supplied in the request; it does not
  query any real ledger.
- It is a support-agent copilot, not an autonomous financial authority; ambiguous
  evidence intentionally returns `insufficient_data` rather than guessing.
- Bangla/Banglish in the deterministic fallback is keyword/normalization based;
  the LLM provides richer same-language replies when enabled.

## Data & secrets

- All complaints and transactions used are **synthetic**. No real customer data
  and no real payment-system integration.
- **No secrets are committed.** API keys come from environment variables only;
  `.env` is git-ignored. Responses, logs, and errors never leak secrets, tokens,
  or stack traces.
