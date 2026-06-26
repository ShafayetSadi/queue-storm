"""Shared test fixtures.

Tests run on the deterministic path by default: no OpenRouter key is set, so
``Settings.llm_enabled`` is False and no network call is attempted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Ensure the LLM is disabled for the default test client, even if the shell has
# deployment-like variables exported.
os.environ["USE_LLM"] = "false"
os.environ["OPENROUTER_API_KEY"] = ""

from app.main import app  # noqa: E402
from tests.helpers.client import TestClient

_SAMPLES_PATH = Path(__file__).resolve().parent.parent / "docs" / "SUST_Preli_Sample_Cases.json"


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def sample_cases() -> list[dict]:
    return json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))["cases"]
