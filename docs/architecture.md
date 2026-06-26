# Preliminary Round Architecture

> Goal: build a safe, reliable, evidence-grounded AI/API service that passes automated judging first and remains understandable for manual review.

This architecture is optimized for the Codex Community Hackathon Online Preliminary round. The preliminary round is judged primarily through API calls, hidden test cases, schema correctness, safety behavior, reasoning quality, endpoint reachability, and documentation. Build a simple, robust backend before adding anything else.

---

## 1. Architecture Decision

Use a **single deployable FastAPI service** with internal modules for schema validation, deterministic reasoning, optional AI assistance, safety guardrails, fallback handling, and documentation.

Do **not** deploy separate `api` and `ai` services for the preliminary round unless the official problem explicitly requires long-running jobs, queue processing, speech/OCR pipelines, or separate model serving.

### Why single service?

The judge needs to call a public HTTP API. Every extra service adds deployment complexity, network failure risk, latency, environment variable complexity, and debugging overhead. A modular monolith gives clean internal separation while remaining easy to deploy and judge.

```text
Judge / Test Harness
        |
        v
Public HTTPS FastAPI Service
        |
        +-- /health
        +-- /<main-analysis-endpoint>
              |
              +-- Pydantic schema validation
              +-- Input normalization
              +-- Evidence extraction
              +-- Rule-based reasoning
              +-- Optional LLM analysis
              +-- Decision merger
              +-- Safety guardrails
              +-- Fallback handler
              +-- Exact response schema
```

---

## 2. Scoring-Oriented Design Principles

The architecture must maximize these judging goals:

1. **Evidence reasoning**: reason from the supplied case data, not only keyword matching.
2. **Safety and escalation**: avoid unsafe advice, sensitive credential requests, and unauthorized promises.
3. **API contract and schema**: return exact fields, types, enums, and HTTP behavior.
4. **Performance and reliability**: remain reachable, fast, stable, and safe under unexpected input.
5. **Response quality**: generate useful, neutral, operationally realistic summaries/replies.
6. **Deployment and reproducibility**: judges can call the endpoint or run the fallback easily.
7. **Documentation**: explain setup, model usage, safety logic, limitations, and examples.

Every file and module should exist to support one of these scoring areas.

---

## 3. Repository Structure

```text
hackathon-preli/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── constants.py
│   ├── schemas.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── routes.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── analyzer.py
│   │   ├── reasoning.py
│   │   ├── evidence.py
│   │   ├── safety.py
│   │   ├── confidence.py
│   │   ├── fallback.py
│   │   └── response_builder.py
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── prompts.py
│   │   └── parser.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── text.py
│       └── logging.py
│
├── tests/
│   ├── test_health.py
│   ├── test_schema.py
│   ├── test_reasoning.py
│   ├── test_safety.py
│   ├── test_fallback.py
│   └── test_samples.py
│
├── sample_requests/
│   ├── valid_sample.json
│   ├── edge_cases.json
│   └── safety_cases.json
│
├── scripts/
│   ├── smoke_test.sh
│   └── local_curl_examples.sh
│
├── Dockerfile
├── .dockerignore
├── .gitignore
├── .env.example
├── requirements.txt
├── README.md
└── architecture.md
```

---

## 4. Service Boundary

### Public API surface

Only expose what the official problem statement requires.

```text
GET  /health
POST /<main-analysis-endpoint-from-problem-statement>
```

No login. No dashboard requirement. No manual approval. No private network. The judge must be able to call the endpoint directly.

### Internal modules

The AI functionality lives inside `app/ai/` as a module. It is **not** a separate deployed service.

```text
api/routes.py
  -> core/analyzer.py
      -> core/evidence.py
      -> core/reasoning.py
      -> ai/client.py       optional
      -> ai/parser.py       optional
      -> core/safety.py
      -> core/response_builder.py
      -> core/fallback.py
```

---

## 5. Request Lifecycle

```text
1. Receive JSON request
2. Validate request using Pydantic
3. Normalize text and optional fields
4. Extract evidence and risk signals
5. Run deterministic reasoning
6. Optionally call LLM with timeout
7. Parse and validate LLM output
8. Merge deterministic and LLM outputs
9. Force valid enums and required fields
10. Apply safety guardrails
11. Compute confidence and review flag
12. Return exact response schema
13. If any step fails, return safe fallback JSON
```

The service should never return invalid JSON or crash because of model failure, malformed optional fields, unexpected text, or low confidence.

---

## 6. Module Responsibilities

### `app/main.py`

Creates the FastAPI app and registers routers.

Responsibilities:

- create app instance
- include health router
- include main analysis router
- configure exception handlers if needed
- avoid business logic here

### `app/api/health.py`

Simple readiness endpoint.

Expected response:

```json
{"status": "ok"}
```

This endpoint must be fast and must not depend on external AI APIs, database connections, or slow startup tasks.

### `app/api/routes.py`

Thin route layer.

Responsibilities:

- define the official POST route
- accept the official request schema
- call `analyze_case()`
- return the official response schema
- keep route logic minimal

### `app/schemas.py`

The most important contract file.

Responsibilities:

- request model
- response model
- enum definitions
- validation constraints
- field defaults for optional values
- exact output shape

Rules:

- Enum values must match the problem statement exactly.
- Field names must match the problem statement exactly.
- Do not return extra fields unless the problem permits them.
- Confidence or scores must stay in allowed ranges.
- Missing required fields should produce controlled validation errors.

### `app/constants.py`

Stores problem-specific constants.

Examples:

```python
VALID_CASE_TYPES = {...}
VALID_SEVERITIES = {...}
VALID_DEPARTMENTS = {...}
HIGH_RISK_TERMS = [...]
SENSITIVE_TERMS = [...]
DEFAULT_CONFIDENCE = 0.55
```

### `app/config.py`

Central configuration loaded from environment variables.

Should include:

- `PORT`
- `OPENAI_API_KEY` or `OPENROUTER_API_KEY`
- `MODEL_NAME`
- `AI_ENABLED`
- `AI_TIMEOUT_SECONDS`
- `LOG_LEVEL`

Rules:

- No real secrets in code.
- No real secrets in README.
- `.env.example` contains placeholder names only.
- App must still work without AI keys using rule-based fallback.

### `app/core/analyzer.py`

Main orchestration layer.

Responsibilities:

- coordinate evidence extraction, reasoning, AI call, safety, fallback, and response building
- ensure the final response always matches the schema
- ensure the service remains useful even if AI fails

Pseudo-flow:

```python
async def analyze_case(payload):
    try:
        normalized = normalize_payload(payload)
        evidence = extract_evidence(normalized)
        rule_decision = reason_from_evidence(normalized, evidence)
        ai_decision = await try_ai_analysis(normalized, evidence, rule_decision)
        merged = merge_decisions(rule_decision, ai_decision)
        safe = apply_safety_guardrails(merged, normalized, evidence)
        return build_response(payload, safe)
    except Exception:
        return safe_fallback_response(payload)
```

### `app/core/evidence.py`

Extracts useful signals from the input.

Responsibilities:

- detect entities mentioned in the problem domain
- detect amounts, dates, IDs, symptoms, issue types, risk indicators, or other domain-specific evidence
- detect conflicting or multiple issues
- preserve evidence snippets for reasoning and summaries

This module should avoid blind keyword-only classification. Use patterns, phrases, context, and combinations of signals.

### `app/core/reasoning.py`

Deterministic decision engine.

Responsibilities:

- classify case type / decision / category
- assign severity or risk score
- assign department / route / action
- set human review flags
- handle ambiguous cases
- handle low-confidence cases

Reasoning rules should be explicit and easy to audit.

Recommended priority order:

1. Critical safety or fraud risk
2. Sensitive information / credential risk
3. Explicit high-priority loss / harm / failure cases
4. Standard supported categories
5. Ambiguous or unknown cases
6. Safe fallback category

### `app/ai/client.py`

Optional LLM provider integration.

Responsibilities:

- call OpenAI/OpenRouter only when enabled
- enforce strict timeout
- use low temperature
- request JSON-only output
- catch all provider errors
- return `None` on failure instead of crashing

Rules:

- Do not let the LLM directly control final enum values.
- Do not depend on the LLM for `/health`.
- Do not block longer than the round timeout budget.
- Use deterministic fallback when the provider fails.

### `app/ai/prompts.py`

Contains system and user prompts.

Prompt rules:

- Include the official enum values.
- Instruct the model to reason only from supplied evidence.
- Instruct the model not to ask for secrets or sensitive credentials.
- Instruct the model not to promise unauthorized actions.
- Require compact JSON.
- Require uncertainty handling.

### `app/ai/parser.py`

Validates and sanitizes LLM output.

Responsibilities:

- parse JSON safely
- reject invalid enum values
- clamp confidence to valid range
- remove unsafe text
- return `None` if parsing fails

### `app/core/safety.py`

Safety guardrail layer.

Responsibilities:

- detect requests for OTP, PIN, passwords, card numbers, API keys, private tokens, or secret credentials
- prevent unsafe customer instructions
- prevent unauthorized promises
- prevent suspicious third-party contact recommendations
- escalate risky or unclear cases
- sanitize summaries/replies before returning

Safety rules:

```text
Never ask users for OTP, PIN, password, secret credentials, full card number, or private authentication details.
Never promise irreversible actions, approvals, refunds, account changes, or guaranteed outcomes unless the problem explicitly authorizes it.
Route risky, critical, suspicious, or low-confidence cases to human review.
Guide users only to official support channels where applicable.
```

### `app/core/confidence.py`

Computes confidence based on evidence quality.

Recommended logic:

```text
High confidence: strong direct evidence for one category and no conflict.
Medium confidence: enough evidence but wording is indirect or multilingual.
Low confidence: ambiguous, missing important fields, multiple possible categories, or weak evidence.
```

Low confidence should usually trigger review or safe fallback depending on the problem statement.

### `app/core/response_builder.py`

Final output formatter.

Responsibilities:

- create exact response model
- force valid enums
- set all required fields
- prevent `None` where not allowed
- generate compact operational summary
- avoid extra fields

### `app/core/fallback.py`

Safe failure handling.

Responsibilities:

- return controlled JSON when AI fails
- return controlled JSON when reasoning fails
- avoid 500 errors for valid requests
- use a safe generic category or review outcome
- set conservative confidence
- escalate if uncertain or risky

Fallback example pattern:

```text
case/category: other or official fallback enum
severity/risk: medium or official safe default
human_review_required: true if uncertain/risky
confidence: low but valid, e.g. 0.35-0.55
summary/reply: neutral and safe
```

---

## 7. AI Strategy

Use a **hybrid rule + AI architecture**.

### Deterministic code must handle

- schema validation
- enum validation
- routing constraints
- safety constraints
- fallback behavior
- critical escalation
- confidence bounds

### AI can help with

- multilingual understanding
- summarization
- evidence interpretation
- ambiguous wording
- extracting structured signals from natural language

### AI must not be trusted for

- final schema validity
- final enum validity
- safety policy
- authorization decisions
- service availability

### AI timeout policy

Recommended values:

```text
AI request timeout: 6-8 seconds
Total POST target: under 5 seconds when possible
Absolute maximum: below official timeout
Fallback: always available
```

### AI failure behavior

If AI fails because of rate limit, quota, timeout, invalid JSON, network error, or missing API key:

```text
Continue with deterministic reasoning.
Return valid JSON.
Do not expose internal errors.
Do not leak stack traces.
```

---

## 8. Safety Architecture

Safety is a final gate before output.

```text
Raw input
  -> risk detection
  -> reasoning
  -> optional AI
  -> final safety filter
  -> safe response
```

### Sensitive data detector

Detect terms such as:

```text
OTP, PIN, password, passcode, CVV, full card number, API key, access token, secret key, private key, recovery code
```

### Unsafe output detector

Before returning, scan generated text for unsafe instructions such as:

```text
share your OTP
send your PIN
give your password
provide your full card number
send your secret key
contact this unknown number
refund has been completed
account has been changed
```

If detected, replace with a safe message and escalate.

### Escalation policy

Set review/escalation flag when:

- problem statement says it is required
- severity/risk is critical
- fraud/security/safety issue is detected
- user mentions credentials or secret information
- output confidence is low
- multiple conflicting case types are present
- AI and rule-based decisions disagree significantly

---

## 9. Performance and Reliability Design

### Startup

- Do not download large models at startup.
- Do not require GPU.
- Do not call external AI inside `/health`.
- Keep app import fast.

### Request handling

- Keep normal requests under 5 seconds where possible.
- Use model timeouts.
- Avoid long chains of multiple LLM calls.
- Avoid database dependency unless required.
- Avoid external APIs unless needed.

### Error handling

- Valid requests should not produce 5xx errors.
- Unexpected optional input should be handled safely.
- Malformed JSON should return controlled framework validation errors.
- Internal exceptions should be logged but not exposed in responses.

### Logging

Log only safe operational information:

```text
request received
decision category
severity/risk
AI used or fallback used
latency
error type without secrets
```

Never log:

```text
API keys
full secret values
private credentials
stack traces in public response
real customer data
```

---

## 10. Deployment Architecture

### Preferred path

Deploy one public FastAPI service to Railway, Render, Fly.io, EC2, Poridhi Lab, or another reachable HTTPS platform.

### Required runtime command

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Docker fallback

Include a lightweight Dockerfile.

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```

### `.dockerignore`

```text
.git
__pycache__
.pytest_cache
.env
.env.*
*.pyc
.venv
node_modules
```

### `.env.example`

```text
PORT=8000
AI_ENABLED=false
OPENAI_API_KEY=
OPENROUTER_API_KEY=
MODEL_NAME=
AI_TIMEOUT_SECONDS=8
LOG_LEVEL=INFO
```

No real secrets should ever be committed.

---

## 11. Testing Strategy

Tests should target the judge, not only happy paths.

### Required local tests

```text
GET /health returns {"status":"ok"}
POST main endpoint accepts official sample request
Response contains all required fields
Response field types are correct
Response enum values exactly match official spec
No extra fields if strict schema is required
Safety cases do not ask for credentials
Critical/risky cases trigger review
Missing optional fields do not crash
Ambiguous input returns safe fallback or review
AI failure still returns valid JSON
```

### Hidden-test oriented edge cases

Prepare sample cases for:

```text
Bangla input
mixed Bangla-English input
empty message
very long message
multiple issues in one message
unclear issue
critical security issue
sensitive credential mention
unsupported category
LLM timeout
invalid enum attempted by LLM
missing optional fields
```

### Smoke test script

`scripts/smoke_test.sh`:

```bash
#!/usr/bin/env bash
set -e

BASE_URL=${1:-http://localhost:8000}

echo "Testing health..."
curl -s "$BASE_URL/health" | grep -q 'ok'

echo "Testing main endpoint..."
curl -s -X POST "$BASE_URL/<main-analysis-endpoint>" \
  -H "Content-Type: application/json" \
  -d @sample_requests/valid_sample.json

echo "Smoke test completed."
```

Replace `<main-analysis-endpoint>` immediately after the official problem is released.

---

## 12. README Requirements

The README should be written for judges.

Minimum sections:

```text
# Project Name
## Problem Summary
## Architecture Summary
## Tech Stack
## API Endpoints
## Request/Response Schema
## Sample Request
## Sample Response
## Reasoning Logic
## AI/Model Usage
## Safety Guardrails
## Fallback Behavior
## Local Setup
## Environment Variables
## Run Command
## Docker Run
## Deployment URL
## Testing
## Known Limitations
## No Secrets / Synthetic Data Confirmation
```

Keep it short but complete. Manual reviewers should understand how the system works in under two minutes.

---

## 13. Team Workflow During the 4-Hour Round

### Role 1: API / Backend Lead

Owns:

- FastAPI project setup
- Pydantic models
- official endpoints
- deployment
- Dockerfile
- smoke testing deployed URL

### Role 2: Reasoning / Logic Lead

Owns:

- evidence extraction
- deterministic rules
- severity/risk logic
- routing/review logic
- confidence scoring
- hidden-style test cases

### Role 3: AI / Safety / Docs Lead

Owns:

- LLM prompt and client
- timeout/fallback behavior
- safety filters
- README
- sample requests/responses
- submission checklist

### Solo team order

```text
schema first -> working route -> deterministic reasoning -> safety -> deployment -> README -> AI polish
```

---

## 14. Four-Hour Execution Plan

### 0:00-0:20 — Problem decoding

- Read the problem fully.
- Extract endpoint names.
- Extract request fields.
- Extract response fields.
- Extract enum values.
- Extract safety rules.
- Extract timeout/deployment/submission requirements.
- Freeze schema in `app/schemas.py`.

### 0:20-1:00 — API skeleton

- Implement `/health`.
- Implement main POST endpoint.
- Return dummy valid JSON.
- Add README skeleton.
- Add `.env.example`.
- Push first working commit.

### 1:00-2:00 — Reasoning engine

- Implement evidence extraction.
- Implement deterministic decision rules.
- Implement severity/risk/review logic.
- Add confidence scoring.
- Test official sample cases.

### 2:00-2:45 — AI and safety

- Add optional LLM call if useful.
- Add timeout and fallback.
- Add JSON parser and enum validation.
- Add safety output filter.
- Add safety test cases.

### 2:45-3:30 — Deployment

- Deploy public endpoint.
- Test `/health` externally.
- Test POST externally.
- Fix port binding and env vars.
- Prepare Docker fallback if deployment is risky.

### 3:30-4:00 — Final polish and submission

- Finish README.
- Add sample request/response.
- Confirm no secrets committed.
- Submit GitHub URL.
- Submit live API base URL.
- Submit model/AI usage details.
- Submit known limitations honestly.

---

## 15. Acceptance Criteria

A solution is acceptable only if all of these are true:

```text
[ ] Public API is reachable through HTTPS or fallback is clearly runnable.
[ ] GET /health returns exactly {"status":"ok"}.
[ ] POST endpoint path exactly matches the official problem statement.
[ ] Response schema exactly matches the official problem statement.
[ ] All enum values are valid official enum values.
[ ] Valid requests do not crash with 5xx.
[ ] Optional fields can be missing without crashing.
[ ] AI provider failure does not break the service.
[ ] Safety filter prevents credential requests and unsafe promises.
[ ] Risky, critical, or uncertain cases are escalated according to the spec.
[ ] README explains setup, run command, AI/model usage, safety logic, and limitations.
[ ] `.env.example` exists and contains no real secrets.
[ ] Repository contains no API keys, tokens, `.env`, stack traces, or real customer data.
```

---

## 16. What Not To Build Unless Required

Avoid these unless the problem statement explicitly requires them:

```text
Frontend dashboard
Authentication system
User accounts
Postgres database
Vector database
OpenSearch
Microservices
Message queues
Kubernetes
Complex agent framework
Multiple LLM calls per request
Heavy local models
GPU-dependent models
Large file storage
```

These may look impressive but can reduce reliability, increase latency, and waste time in the preliminary round.

---

## 17. Final Architecture Summary

Build a single FastAPI service with strict schema validation, deterministic evidence-based reasoning, optional AI support, safety guardrails, and safe fallback behavior.

The system should be boring, fast, reliable, and judge-friendly:

```text
Correct JSON > Fancy UI
Safety > Overconfident automation
Deterministic fallback > Pure LLM dependency
Reachable endpoint > Complex architecture
Clear README > Unexplained cleverness
```

This architecture is designed to pass automated tests first, then survive manual review by being understandable, safe, reproducible, and honest about limitations.
