# RUNBOOK — QueueStorm Investigator

A stranger can copy-paste these steps to bring the service up. Required even if a
Live URL is submitted, so judges can redeploy if the URL goes down.

## Option A — Docker Compose (recommended)

```bash
git clone <this-repo-url>
cd queue-storm

# Provide env. The service runs WITHOUT a key (deterministic path).
# For the full hybrid, set OPENROUTER_API_KEY in .env.
cp .env.example .env

docker compose up --build -d

# Verify
curl -fsS http://localhost:8000/health         # -> {"status":"ok"}
BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh
```

Stop: `docker compose down`.

## Option B — Plain Docker

```bash
cd queue-storm
cp .env.example .env            # optionally set OPENROUTER_API_KEY
docker build -t queuestorm-investigator .
docker run -d -p 8000:8000 --env-file .env --name queuestorm queuestorm-investigator
curl -fsS http://localhost:8000/health
```

## Option C — Local Python (no Docker)

```bash
cd queue-storm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `8000` | Service port. |
| `USE_LLM` | `true` | Set `false` to force the deterministic path. |
| `OPENROUTER_API_KEY` | *(empty)* | Required only if `USE_LLM=true`. Without it the service runs deterministically. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible endpoint. |
| `MODEL_NAME` | `anthropic/claude-haiku-4.5` | Any OpenRouter model id. |
| `LLM_TIMEOUT_SECONDS` | `5` | Per-call timeout; well under the 30s harness limit. |

## Health & sample verification

```bash
curl -fsS http://localhost:8000/health
python scripts/run_sample_cases.py --base-url http://localhost:8000
```

## Troubleshooting

- **`/health` not ready:** check container logs (`docker compose logs -f`); the
  service binds `0.0.0.0:${PORT}` and needs no external dependency to start.
- **LLM errors / timeouts:** harmless — the service automatically falls back to
  the deterministic engine and adds a `llm_fallback` reason code. To run purely
  deterministically, set `USE_LLM=false`.
- **Port already in use:** set a different `PORT` in `.env` (Compose maps
  `${PORT}:8000`).
