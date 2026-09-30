"""Unit tests for src/engine/semantic_cache.py."""
import pytest
from sklearn.metrics.pairwise import cosine_similarity

from src.engine.semantic_cache import (
    SemanticCache,
    _cache_symptom_families,
    _explicit_device_profile,
    normalize_query,
)
from src.schema import Action, ContextDeeplinkResponse, Goal, StepGroup


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


def test_l2_rejects_high_similarity_when_symptom_families_conflict():
    response = _make_dummy_response("Display troubleshooting")
    cases = [
        (
            "A Galaxy tablet screen goes dark while several app icons still appear",
            "A Galaxy phone screen flickers and goes dark when its mail app opens",
        ),
        (
            "The handset screen is cracked and flashes intermittently",
            "Touch response feels sluggish and delayed on my handset screen",
        ),
    ]

    for cached_query, paraphrase in cases:
        cache = SemanticCache(similarity_threshold=0.40)
        cache.put(cached_query, response)
        cache._rebuild_index()
        similarity = float(
            cosine_similarity(
                cache._vectorizer.transform([normalize_query(paraphrase)]),
                cache._tfidf_matrix,
            )[0][0]
        )
        matched, hit, _ = cache.get(paraphrase)

        assert similarity >= cache.similarity_threshold
        assert hit is False
        assert matched is None
        assert cache.l2_compatibility_rejections == 1


def test_l2_rejects_different_form_factor_and_explicit_model():
    response = _make_dummy_response("Display troubleshooting")
    device_cache = SemanticCache(similarity_threshold=0.30)
    device_cache.put(
        "A Galaxy tablet display looks tiny and fills only part of the screen",
        response,
    )
    device_match, device_hit, _ = device_cache.get(
        "A Galaxy phone display looks tiny and fills only part of the screen"
    )
    assert device_hit is False
    assert device_match is None

    model_cache = SemanticCache(similarity_threshold=0.30)
    model_cache.put("Touch response is sluggish on a Galaxy S22 screen", response)
    model_match, model_hit, _ = model_cache.get(
        "Touch response is sluggish on a Galaxy S24 screen"
    )
    assert model_hit is False
    assert model_match is None


def test_l2_skips_incompatible_top_candidate_and_hits_next_compatible_scenario():
    cache = SemanticCache(similarity_threshold=0.40)
    phone_response = _make_dummy_response("Phone display troubleshooting")
    tablet_response = _make_dummy_response("Tablet display troubleshooting")
    cache.put(
        "A phone screen stays mostly dark and just a handful of app icons remain lit",
        phone_response,
        device="Galaxy phone",
    )
    cache.put(
        "The tablet display stays dark and a few application icons remain illuminated",
        tablet_response,
        device="Galaxy Tab",
    )

    matched, hit, _ = cache.get(
        "The tablet screen stays mostly dark and a handful of app icons remain lit.",
        device="Galaxy Tab",
    )

    assert hit is True
    assert matched is tablet_response
    assert cache.l2_candidates_evaluated >= 2
    assert cache.l2_compatibility_rejections >= 1


def test_l2_misses_after_all_top_candidates_fail_and_pipeline_runs_rag():
    from src.engine.pipeline import FixFlowPipeline

    pipeline = FixFlowPipeline(prewarm=False)
    pipeline.cache = SemanticCache(similarity_threshold=0.40)
    pipeline.cache.put(
        "A phone screen stays dark while I open the mail inbox",
        _make_dummy_response("Phone display troubleshooting"),
        device="Galaxy phone",
    )
    pipeline.cache.put(
        "A tablet screen stays dark while I open an app",
        _make_dummy_response("Tablet display troubleshooting"),
        device="Galaxy Tab",
    )

    _, metadata = pipeline.troubleshoot(
        "A tablet screen stays dark while I open the email inbox",
        device="Galaxy Tab",
    )

    assert metadata["cache_hit"] is False
    assert metadata["source"] == "rag_pipeline"
    assert pipeline.cache.l2_compatibility_rejections == 2
    assert pipeline.cache.l2_candidates_evaluated == 2


def test_l2_uses_explicit_device_context_but_l1_remains_exact():
    response = _make_dummy_response("Display troubleshooting")
    cache = SemanticCache(similarity_threshold=0.20)
    cache.put("Adjust the viewing brightness", response, device="Samsung TV")

    match, hit, _ = cache.get(
        "Set the viewing brightness", device="Galaxy phone"
    )
    assert hit is False
    assert match is None

    cache.put("Exact cache key stays exact", response, device="Samsung TV")
    exact_match, exact_hit, _ = cache.get(
        "Exact cache key stays exact", device="Galaxy phone"
    )
    assert exact_hit is True
    assert exact_match is response


def test_l2_compatibility_miss_allows_pipeline_retrieval():
    from src.engine.pipeline import FixFlowPipeline

    pipeline = FixFlowPipeline(prewarm=True)
    query = "A Galaxy phone screen flickers and goes dark when its mail app opens"

    _, metadata = pipeline.troubleshoot(query)

    assert metadata["cache_hit"] is False
    assert metadata["source"] == "rag_pipeline"
    assert "retrieved_title" in metadata
    assert pipeline.cache.l2_compatibility_rejections >= 1


def test_p95_latency_tracking():
    cache = SemanticCache()
    resp = _make_dummy_response("Screen fix")
    cache.put("screen problem", resp)

    for _ in range(50):
        cache.get("screen problem")

    assert cache.p95_latency_ms() < 50.0
    assert cache.hit_rate() == 1.0


def test_cache_metrics_count_l1_l2_rejections_reasons_and_misses():
    cache = SemanticCache(similarity_threshold=0.20)
    response = _make_dummy_response("Touch response troubleshooting")
    cache.put(
        "Touch response is slow on a Galaxy phone",
        response,
        device="Galaxy phone",
    )

    _, exact_hit, _ = cache.get("Touch response is slow on a Galaxy phone")
    assert exact_hit is True

    _, semantic_hit, _ = cache.get(
        "Touch response feels sluggish on a Galaxy phone",
        device="Galaxy phone",
    )
    assert semantic_hit is True

    _, incompatible_hit, _ = cache.get(
        "Touch response feels sluggish on a Galaxy tablet",
        device="Galaxy Tab",
    )
    assert incompatible_hit is False

    metrics = cache.metrics_snapshot()
    assert metrics == {
        "l1_exact_hits": 1,
        "l2_hits": 1,
        "l2_candidates_evaluated": 2,
        "l2_candidates_rejected": 1,
        "l2_rejection_reasons": {"device_family_mismatch": 1},
        "total_cache_misses": 1,
    }


def test_scenario_representation_can_match_a_symptom_paraphrase_at_configured_threshold():
    cache = SemanticCache(similarity_threshold=0.40)
    response = _make_dummy_response("Dark display panel troubleshooting")
    cache.put("Samsung handset screen turns black and remains unlit", response)

    query = "The phone panel stays dark"
    cache._rebuild_index()
    alias_similarity = float(
        cosine_similarity(
            cache._vectorizer.transform([normalize_query(query)]),
            cache._tfidf_matrix,
        )[0][0]
    )
    match, hit, _ = cache.get(query)

    assert cache.similarity_threshold == 0.40
    assert alias_similarity < cache.similarity_threshold
    assert hit is True
    assert match is response


def test_slash_separated_model_metadata_preserves_each_explicit_model():
    detector = SemanticCache()._device_detector
    _, candidate_models = _explicit_device_profile(
        "My Galaxy A15/A16 screen stays black", detector
    )
    _, query_models = _explicit_device_profile("Galaxy A16 screen is black", detector)

    assert candidate_models == {"a15", "a16"}
    assert query_models == {"a16"}

    cache = SemanticCache(similarity_threshold=0.40)
    response = _make_dummy_response("Blank or black display")
    cache.put("My Galaxy A15/A16 screen stays black", response)
    match, hit, _ = cache.get("Galaxy A16 display is completely dark")
    assert hit is True
    assert match is response


def test_symptom_family_context_avoids_split_icons_and_carrier_switch_collisions():
    partial_display = _cache_symptom_families(
        "A split screen has one dark half and only a few icons remain visible"
    )
    split_window = _cache_symptom_families(
        "Run two apps in split-screen windows"
    )
    carrier_change = _cache_symptom_families(
        "The display is blank after switching mobile carriers"
    )
    smart_switch = _cache_symptom_families(
        "The black screen prevents using Smart Switch to transfer data"
    )

    assert "black_screen" in partial_display
    assert "multitasking" not in partial_display
    assert "multitasking" in split_window
    assert "multitasking" not in partial_display
    assert "transfer" not in carrier_change
    assert "transfer" in smart_switch


def test_symptom_families_normalize_general_display_equivalents_with_context():
    assert "touch_input" in _cache_symptom_families(
        "Digitizer input is not responding"
    )
    assert "damage" in _cache_symptom_families(
        "A fracture has damaged the display near its crease"
    )
    assert "damage" not in _cache_symptom_families(
        "The usual crease is visible when unfolding the phone"
    )
    assert "display_flicker" in _cache_symptom_families(
        "The display strobes rapidly"
    )
    assert "display_distortion" in _cache_symptom_families(
        "Visual artifacts appear across the display panel"
    )
    assert "display_distortion" not in _cache_symptom_families(
        "The video contains visual artifacts"
    )


def test_scenario_vector_includes_symptom_families_from_action_names():
    response = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow the display troubleshooting steps",
                title="Screen troubleshooting",
                score=0.9,
                actions=[
                    Action(
                        actionName="Inspect cracked display and digitizer input",
                        description="Inspect display and touch input",
                        stepGroups=[StepGroup(steps=["Inspect the display panel"])],
                    )
                ],
            )
        ]
    )
    cache = SemanticCache(similarity_threshold=0.40)
    cache.put("A flexible display has a physical crease fracture", response)
    metadata = cache._scenario_metadata[0]
    feature_text = " ".join(
        f"symptomfamily{family}"
        for family in sorted(
            metadata.symptom_families
            | metadata.title_symptom_families
            | metadata.action_symptom_families
        )
    )

    assert {"damage", "touch_input"} <= metadata.action_symptom_families
    assert "symptomfamilydamage" in feature_text
    assert "symptomfamilytouch_input" in feature_text
