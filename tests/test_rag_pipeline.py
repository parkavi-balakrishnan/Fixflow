"""Integration tests for end-to-end RAG pipeline in FixFlow."""
import pytest

from src.engine.pipeline import FixFlowPipeline
from src.engine.validator import validate_response


@pytest.fixture(scope="module")
def pipeline():
    return FixFlowPipeline(prewarm=False)


def test_rag_pipeline_cold_path_retrieval_and_validation(pipeline):
    """Verifies that an unseen query goes through RAG retrieval, extraction, and passes validation."""
    query = "My Galaxy S22 screen inputs are delayed and the touch responsiveness is laggy"

    # Step 1: First call -> Cache Miss, runs full RAG pipeline
    resp, meta = pipeline.troubleshoot(query)

    assert meta["cache_hit"] is False
    assert meta["source"] == "rag_pipeline"
    assert "retrieval_latency_ms" in meta
    assert meta["retrieval_score"] > 0.0
    assert meta["retrieved_doc_id"] == "row_21"

    # Must validate cleanly against all Rubric and Schema rules
    val_res = validate_response(resp)
    assert val_res.is_valid is True
    assert len(resp.contexts) > 0
    assert "Touchscreen" in resp.contexts[0].title or "Touch" in resp.contexts[0].title


def test_rag_pipeline_caches_and_hits_on_repeat():
    """Verifies that subsequent identical or paraphrase queries hit the fast-path semantic cache."""
    clean_pipe = FixFlowPipeline(cache_threshold=0.65, prewarm=False)
    query = "My Galaxy A17 screen looks distorted right after I received the phone"

    # Cold path
    resp1, meta1 = clean_pipe.troubleshoot(query)
    assert meta1["cache_hit"] is False
    assert meta1["retrieved_doc_id"] == "row_20"

    # Repeat exact query -> must hit L1 cache
    resp2, meta2 = clean_pipe.troubleshoot(query)
    assert meta2["cache_hit"] is True
    assert meta2["source"] == "semantic_cache"
    assert meta2["latency_ms"] < 50.0


def test_rag_pipeline_device_aware_query(pipeline):
    """Tests device parameter passed to pipeline.troubleshoot()."""
    query = "screen stays small and does not expand to fill the entire TV"
    resp, meta = pipeline.troubleshoot(query, device="Samsung TV")

    assert meta["cache_hit"] is False
    assert "retrieval_latency_ms" in meta
    assert meta["retrieved_doc_id"] == "row_8"

    val_res = validate_response(resp)
    assert val_res.is_valid is True
    assert "Screen mirroring" in resp.contexts[0].title or "Screen" in resp.contexts[0].title


def test_rag_pipeline_closest_siis_delegation(pipeline):
    """Verifies backward-compatible _retrieve_closest_siis delegates to RAG retriever."""
    payload = pipeline._retrieve_closest_siis("My Galaxy phone screen is completely cracked")
    assert payload is not None
    assert "Cracked or bleeding screen" in payload.get("title", "")
