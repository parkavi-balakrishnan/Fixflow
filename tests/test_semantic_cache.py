"""Unit tests for src/engine/semantic_cache.py."""
import pytest

from src.engine.semantic_cache import SemanticCache, normalize_query
from src.schema import ContextDeeplinkResponse, Goal


def _make_dummy_response(title: str) -> ContextDeeplinkResponse:
    return ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal=f"Follow these steps to perform this {title} Troubleshooting",
                title=title,
                score=0.9,
                actions=[],
            )
        ]
    )


def test_normalize_query():
    assert normalize_query("  My Phone is SLOW!!  ") == "my phone is slow"
    assert normalize_query("Screen cracked... What to do?") == "screen cracked what to do"


def test_l1_exact_match_hit():
    cache = SemanticCache()
    resp = _make_dummy_response("Battery drain fix")
    cache.put("my battery is draining quickly", resp)

    # Exact string match (case-insensitive)
    matched, hit, latency = cache.get("My Battery Is Draining Quickly")
    assert hit is True
    assert matched is not None
    assert matched.contexts[0].title == "Battery drain fix"
    assert latency < 50.0  # Well below 300ms


def test_l2_semantic_paraphrase_hit():
    cache = SemanticCache(similarity_threshold=0.50)
    resp = _make_dummy_response("Screen display damage")
    canonical = "The mobile phone screen is cracked and flashes intermittently"
    variations = [
        "phone display is broken and flickering constantly",
        "glass cracked on phone and screen blinks",
    ]
    cache.put(canonical, resp, variations=variations)

    # Paraphrase test: unseen phrasing
    unseen_paraphrase = "mobile display cracked and screen flashes"
    matched, hit, latency = cache.get(unseen_paraphrase)
    assert hit is True
    assert matched is not None
    assert matched.contexts[0].title == "Screen display damage"
    assert latency < 100.0  # Well below 300ms


def test_cache_miss_on_unrelated_query():
    cache = SemanticCache()
    resp = _make_dummy_response("Battery drain fix")
    cache.put("my battery is draining quickly", resp)

    matched, hit, latency = cache.get("how do I change camera zoom mode")
    assert hit is False
    assert matched is None


def test_p95_latency_tracking():
    cache = SemanticCache()
    resp = _make_dummy_response("Screen fix")
    cache.put("screen problem", resp)

    for _ in range(50):
        cache.get("screen problem")

    assert cache.p95_latency_ms() < 50.0
    assert cache.hit_rate() == 1.0
