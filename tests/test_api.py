"""Unit and integration tests for src/api.py."""
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.engine.validator import detect_url_leakage, validate_response
from src.schema import ContextDeeplinkResponse


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint_gate_g2(client):
    """Gate G2: GET /health returns {'status': 'ok'}."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_troubleshoot_canonical_query_cache_hit(client):
    """POST /v1/troubleshoot on prewarmed query returns cached response."""
    payload = {
        "query": "The mobile phone screen is cracked and flashes intermittently.",
    }
    resp = client.post("/v1/troubleshoot", json=payload)
    assert resp.status_code == 200
    assert resp.headers.get("x-cache-hit") == "true"

    data = resp.json()
    assert "contexts" in data
    assert len(data["contexts"]) > 0

    # Validate schema
    model = ContextDeeplinkResponse.model_validate(data)
    val_res = validate_response(model)
    assert val_res.is_valid is True


def test_troubleshoot_unseen_scenario_and_repeat_cache(client):
    """Cold query with custom SIIS payload, followed by repeat query cache hit."""
    unseen_payload = {
        "query": "My Galaxy Tab screen shows purple vertical lines",
        "siis_response": {
            "title": "Galaxy Tab screen line defects",
            "content": (
                "## Step 1: Check Display in Settings\n"
                "Navigate to Settings on your tablet.\n"
                "Tap Display and check color mode settings.\n"
                "## Step 2: Contact Samsung Service Center\n"
                "Visit an authorized Samsung Service Center for hardware inspection.\n"
            ),
        },
    }

    # 1. Cold call
    resp1 = client.post("/v1/troubleshoot", json=unseen_payload)
    assert resp1.status_code == 200
    assert resp1.headers.get("x-cache-hit") == "false"
    data1 = resp1.json()

    # Zero URL leaks gate G5 check
    json_str = resp1.text
    # Ignore internal bixby:// scheme
    leaks = detect_url_leakage(json_str)
    assert len(leaks) == 0, f"URL leaks detected in API output: {leaks}"

    # 2. Repeat call (same query) must HIT cache
    resp2 = client.post("/v1/troubleshoot", json={"query": unseen_payload["query"]})
    assert resp2.status_code == 200
    assert resp2.headers.get("x-cache-hit") == "true"
