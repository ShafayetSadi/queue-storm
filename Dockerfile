# QueueStorm Investigator — single deployable service.
# No models are baked in; the optional LLM is called over HTTP at runtime, so the
# image stays small (well under the 5 GB guidance).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# curl is used by the container HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY docs ./docs

# Run as a non-root user.
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

# Shell form so ${PORT} is expanded at runtime.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2
