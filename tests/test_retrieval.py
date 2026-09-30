"""Comprehensive tests and evaluation suite for SIISRetriever (RAG Retrieval Layer)."""
import os
import pytest

from src.engine.retriever import SIISRetriever

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
)


@pytest.fixture(scope="module")
def retriever():
    return SIISRetriever(data_dir=DATA_DIR)


def test_retrieval_top1_and_top3_accuracy_on_input_txt(retriever):
    """Evaluates retrieval accuracy across all 20 canonical queries from data/input.txt."""
    input_path = os.path.join(DATA_DIR, "input.txt")
    with open(input_path, "r", encoding="utf-8") as f:
        queries = [l.strip() for l in f if l.strip()]

    assert len(queries) == 20
    docs = retriever.knowledge_store.documents
    assert len(docs) == 20

    top1_correct = 0
    top3_correct = 0

    for idx, query in enumerate(queries):
        expected_doc = docs[idx]
        result = retriever.retrieve(query, top_k=3)

        top1_id = result.matched_doc.doc_id
        top3_ids = [c.doc_id for c in result.candidates[:3]]

        if top1_id == expected_doc.doc_id:
            top1_correct += 1
        if expected_doc.doc_id in top3_ids:
            top3_correct += 1

    top1_accuracy = top1_correct / len(queries)
    top3_accuracy = top3_correct / len(queries)

    # Must exceed 95% Top-1 and 100% Top-3
    assert top1_accuracy >= 0.95, f"Top-1 accuracy too low: {top1_accuracy:.2%}"
    assert top3_accuracy == 1.00, f"Top-3 accuracy must be 100%, got {top3_accuracy:.2%}"


def test_retrieval_paraphrased_queries(retriever):
    """Evaluates semantic generalization on diverse unseen paraphrased queries."""
    paraphrase_cases = [
        ("My Galaxy S22 screen is lagging when I touch it", "Touchscreen issues on a Galaxy phone or tablet"),
        ("Phone glass cracked after falling on the floor", "Cracked or bleeding screen on Galaxy phone or tablet"),
        ("Camera video flickers when recording in the room", "Screen flickers when using the Camera on a Galaxy phone"),
        ("How to transfer files with QR code on tablet", "Transfer Secure folder with Smart Switch"),
        ("Screen will not rotate when turning sideways", "Screen does not rotate on Galaxy phone or tablet"),
        ("Floating icon button on screen", "Use Multi window and App pairs on your Galaxy phone or tablet"),
        ("Cast phone screen to Samsung Smart TV", "Screen mirroring to your Samsung TV"),
        ("Cannot access my email account on tablet", "Email server not responding on Samsung phone or tablet"),
    ]

    for query, expected_title_sub in paraphrase_cases:
        result = retriever.retrieve(query, top_k=3)
        assert result.matched_doc is not None
        assert expected_title_sub.lower() in result.matched_doc.title.lower(), (
            f"Failed on query '{query}'. Expected '{expected_title_sub}', got '{result.matched_doc.title}'"
        )


def test_retrieval_vague_queries(retriever):
    """Tests retrieval robustness on vague or underspecified queries."""
    vague_cases = [
        ("Device screen is dark and won't turn on", "Blank or black display on a Samsung phone or tablet"),
        ("Display not rotating", "Screen does not rotate on Galaxy phone or tablet"),
        ("Delayed touch input", "Touchscreen issues on a Galaxy phone or tablet"),
    ]
    for query, expected_title in vague_cases:
        result = retriever.retrieve(query, top_k=3)
        assert result.matched_doc is not None
        assert expected_title.lower() in result.matched_doc.title.lower()


def test_device_aware_retrieval_with_explicit_context(retriever):
    """Verifies that providing explicit device context influences retrieval prioritization."""
    # When asking about screen mirroring, specifying 'Samsung TV' directs to TV screen mirroring
    tv_result = retriever.retrieve("small screen aspect ratio", device="Samsung TV")
    assert "mirroring" in tv_result.matched_doc.title.lower() or "tv" in tv_result.matched_doc.title.lower()

    # Query with tablet mention
    tablet_result = retriever.retrieve("flashes and goes blank when opening mail", device="Galaxy Tab")
    assert "email" in tablet_result.matched_doc.title.lower()


def test_unrelated_queries_low_confidence(retriever):
    """Ensures completely unrelated nonsensical queries have lower confidence scores."""
    unrelated_queries = [
        "how to bake chocolate chip cookies at home",
        "order pepperoni pizza online delivery",
        "current weather in Tokyo and Paris",
    ]
    for query in unrelated_queries:
        result = retriever.retrieve(query)
        # Unrelated queries should have low confidence scores (< 0.50)
        assert result.top1_score < 0.50, f"Unrelated query '{query}' scored unexpectedly high: {result.top1_score}"


def test_ranking_and_reranking_structure(retriever):
    """Verifies that candidates list is strictly sorted in descending score order."""
    result = retriever.retrieve("Galaxy S22 touchscreen responsiveness lag", top_k=5)
    assert len(result.candidates) > 1
    scores = [c.score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)
    assert result.top1_score == scores[0]


def test_retrieval_performance_and_p95_latency(retriever):
    """Measures retrieval latency and verifies average and P95 latency thresholds."""
    test_query = "Screen display cracked and broken"
    for _ in range(50):
        retriever.retrieve(test_query)

    avg_lat = retriever.average_latency_ms()
    p95_lat = retriever.p95_latency_ms()

    # Targets: Average < 10ms, P95 < 20ms
    assert avg_lat < 10.0, f"Average retrieval latency too high: {avg_lat} ms"
    assert p95_lat < 20.0, f"P95 retrieval latency too high: {p95_lat} ms"
