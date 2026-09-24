"""Unit tests for src/engine/pipeline.py."""
import pytest

from src.engine.pipeline import FixFlowPipeline
from src.engine.validator import validate_response


@pytest.fixture(scope="module")
def pipeline():
    return FixFlowPipeline(prewarm=True)


def test_pipeline_prewarm(pipeline):
    assert len(pipeline.known_siis) == 20
    assert pipeline.cache.total_requests >= 0


def test_pipeline_prewarmed_cache_hit(pipeline):
    query = "The mobile phone screen is cracked and flashes intermittently."
    resp, meta = pipeline.troubleshoot(query)

    assert meta["cache_hit"] is True
    assert meta["latency_ms"] < 100.0  # Well under 300ms target
    assert len(resp.contexts) > 0

    val_res = validate_response(resp)
    assert val_res.is_valid is True


def test_pipeline_unseen_scenario_cold_path(pipeline):
    unseen_query = "My Galaxy Watch screen flickers when notifications arrive"
    unseen_siis = {
        "title": "Galaxy Watch display flickering issues",
        "content": (
            "## Step 1: Adjust Brightness in Settings\n"
            "Open Settings on your device.\n"
            "Tap Display and adjust brightness level.\n"
            "## Step 2: Restart the Watch\n"
            "Press and hold the Home key to reboot watch into safe state.\n"
        ),
    }

    # First call: cold path
    resp, meta = pipeline.troubleshoot(unseen_query, unseen_siis)
    assert meta["cache_hit"] is False
    assert len(resp.contexts) > 0

    # Must pass all rubric rules
    val_res = validate_response(resp)
    assert val_res.is_valid is True

    # Critical action (restart) must be sorted last
    actions = resp.contexts[0].actions
    assert actions[-1].actionName == "Restart The Watch"

    # Second call: repeat query must HIT cache
    resp2, meta2 = pipeline.troubleshoot(unseen_query)
    assert meta2["cache_hit"] is True
    assert meta2["latency_ms"] < 50.0  # Instant P95
