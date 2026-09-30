"""Unit tests for src/engine/preprocessor.py and src/engine/knowledge_store.py."""
import json
import os
import tempfile
import pytest

from src.engine.knowledge_store import KnowledgeStore
from src.engine.preprocessor import KnowledgeDocument, SIISPreprocessor


@pytest.fixture(scope="module")
def preprocessor():
    return SIISPreprocessor()


@pytest.fixture(scope="module")
def knowledge_store():
    return KnowledgeStore()


def test_preprocessor_parses_all_20_siis_responses(knowledge_store):
    assert knowledge_store.count() == 20
    for doc in knowledge_store.documents:
        assert doc.doc_id.startswith("row_")
        assert len(doc.title) > 0
        assert len(doc.sections) > 0
        assert len(doc.searchable_text) > 0
        assert "title" in doc.raw_siis
        assert "content" in doc.raw_siis


def test_preprocessor_extracts_device_categories(preprocessor):
    content_sample = (
        "Smartphone,Others Mobile,Notebook,Tablet,QLED,Wearable Screen mirroring to your Samsung TV "
        "( Smartphone,Others Mobile,Notebook,Tablet,QLED,Wearable): # Title\nSome content"
    )
    cats = preprocessor.parse_categories(content_sample)
    assert "Smartphone" in cats
    assert "Tablet" in cats
    assert "Wearable" in cats
    assert "QLED" in cats


def test_preprocessor_extracts_sections_without_fabrication(preprocessor):
    raw_content = (
        "Smartphone,Tablet Blank display ( Smartphone,Tablet): ## Step 1: Force a Restart\n"
        "Press and hold Power and Volume down buttons for 20 seconds.\n"
        "## Step 2: Connect Charger\n"
        "Connect the device to an official charger for at least 1 hour.\n"
    )
    sections = preprocessor.parse_sections(raw_content)
    assert len(sections) == 2
    assert "Force a Restart" in sections[0].section_title
    assert any("20 seconds" in s for s in sections[0].steps)
    assert "Connect Charger" in sections[1].section_title
    assert any("1 hour" in s for s in sections[1].steps)


def test_preprocessor_zero_url_leakage(preprocessor):
    content_with_links = (
        "## Step 1: Check updates\n"
        "Visit https://www.samsung.com/support or http://example.com for more info.\n"
        "Also check [Samsung Link](https://samsung.com/app) or email support@samsung.com.\n"
    )
    sections = preprocessor.parse_sections(content_with_links)
    for sec in sections:
        for step in sec.steps:
            assert "https://" not in step
            assert "http://" not in step
            assert "support@samsung.com" not in step
            assert "[" not in step and "](" not in step


def test_preprocessor_serialization_roundtrip(preprocessor):
    doc = KnowledgeDocument(
        doc_id="test_row",
        title="Battery Diagnostic Troubleshooting",
        original_query="My battery drains fast",
        device_categories=["Smartphone", "Tablet"],
        device_models=["galaxy s22"],
        symptoms=["battery drain", "overheating"],
        sections=[],
        searchable_text="Battery drain test content",
        raw_siis={"title": "Battery Diagnostic", "content": "Steps to test"},
    )
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        preprocessor.save_processed([doc], tmp_path)
        loaded = preprocessor.load_processed(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].doc_id == "test_row"
        assert loaded[0].title == "Battery Diagnostic Troubleshooting"
        assert loaded[0].device_models == ["galaxy s22"]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_knowledge_store_indexing_and_lookup(knowledge_store):
    doc_1 = knowledge_store.get_document("row_1")
    assert doc_1 is not None
    assert doc_1.doc_id == "row_1"
    assert "Email" in doc_1.title

    tablet_docs = knowledge_store.get_documents_by_category("tablet")
    assert len(tablet_docs) > 0


def test_knowledge_store_scalability_synthetic():
    """Validates that KnowledgeStore scales cleanly to larger catalogs (e.g. 100+ documents)."""
    synthetic_docs = []
    preprocessor = SIISPreprocessor()
    for i in range(100):
        item = {
            "id": f"synthetic_{i}",
            "original_query": f"Troubleshooting issue number {i} on Galaxy S{20 + (i % 6)}",
            "siis_response": {
                "title": f"Troubleshooting Guide {i}",
                "content": (
                    f"Smartphone,Others Mobile Guide {i} ( Smartphone,Others Mobile):\n"
                    f"## Step 1: Check Setting {i}\n"
                    f"Navigate to Settings and verify configuration option {i}.\n"
                ),
            },
        }
        synthetic_docs.append(preprocessor.process_item(item))

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        preprocessor.save_processed(synthetic_docs, tmp_path)
        loaded = preprocessor.load_processed(tmp_path)
        assert len(loaded) == 100
        assert loaded[50].doc_id == "synthetic_50"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
