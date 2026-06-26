.PHONY: install test test-suite test-suite-live serve docker-build docker-up

# Port the throwaway server in `test-suite` binds to.
PORT ?= 8021
BASE_URL ?= http://localhost:8000

install:
	uv sync --dev

# Unit tests.
test:
	uv run pytest -q

# End-to-end suite: boots a deterministic server, runs the sample cases against
# it, then tears it down. Logs land in ./test-log/ (git-ignored).
# Override the model path with: make test-suite USE_LLM=true
test-suite:
	@echo ">> starting service on port $(PORT)"
	@USE_LLM=$${USE_LLM:-false} uv run uvicorn app.main:app --host 0.0.0.0 --port $(PORT) --log-level warning & \
	SERVER_PID=$$!; \
	trap "kill $$SERVER_PID 2>/dev/null" EXIT; \
	for i in $$(seq 1 40); do \
	  curl -fsS http://localhost:$(PORT)/health >/dev/null 2>&1 && break; \
	  sleep 0.5; \
	done; \
	uv run python scripts/run_test_suite.py --base-url http://localhost:$(PORT)

# Run the suite against an already-running service (e.g. Docker or a Live URL).
# Override with: make test-suite-live BASE_URL=https://your-service
test-suite-live:
	uv run python scripts/run_test_suite.py --base-url $(BASE_URL)

serve:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

docker-build:
	docker build -t queuestorm-investigator .

docker-up:
	docker compose up --build
