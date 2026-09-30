"""Unit tests for src/engine/device_detector.py."""
import pytest

from src.engine.device_detector import DeviceDetector
from src.engine.preprocessor import KnowledgeDocument


@pytest.fixture(scope="module")
def detector():
    return DeviceDetector()


def test_device_detector_extracts_families(detector):
    # Foldable
    ctx_flip = detector.detect("My Galaxy Z Flip 7 screen is blank")
    assert "foldable" in ctx_flip.families or "smartphone" in ctx_flip.families

    # Tablet
    ctx_tab = detector.detect("My Samsung A115G tablet screen flashes")
    assert "tablet" in ctx_tab.families

    # TV
    ctx_tv = detector.detect("Screen mirroring to my Samsung TV with Smart View")
    assert "tv" in ctx_tv.families

    # Wearable
    ctx_watch = detector.detect("My Galaxy Watch screen flickers")
    assert "wearable" in ctx_watch.families

    # Smartphone
    ctx_phone = detector.detect("My Galaxy S22 screen has delayed touch responsiveness")
    assert "smartphone" in ctx_phone.families


def test_device_detector_extracts_models(detector):
    ctx_s24 = detector.detect("My Galaxy S24 Ultra screen won't turn on")
    assert any("s24 ultra" in m for m in ctx_s24.models)

    ctx_flip6 = detector.detect("Galaxy Z Flip 6 inner screen is blank")
    assert any("flip 6" in m for m in ctx_flip6.models)

    ctx_a17 = detector.detect("My Galaxy A17 screen looks distorted")
    assert any("a17" in m for m in ctx_a17.models)


def test_device_affinity_scoring(detector):
    doc_phone = KnowledgeDocument(
        doc_id="phone_doc",
        title="Smartphone Screen Display",
        original_query="phone screen",
        device_categories=["Smartphone", "Others Mobile"],
        device_models=["galaxy s22", "galaxy s24"],
    )
    doc_tv = KnowledgeDocument(
        doc_id="tv_doc",
        title="Screen Mirroring to TV",
        original_query="mirror tv",
        device_categories=["Smartphone", "Samsung TV", "QLED"],
        device_models=["samsung tv"],
    )

    # Smartphone query should score high on phone doc
    ctx_phone = detector.detect("Galaxy S22 display broken")
    assert detector.calculate_affinity(ctx_phone, doc_phone) >= 0.9

    # TV query should score high on TV doc and lower on phone doc
    ctx_tv = detector.detect("How to cast screen to Samsung Smart TV")
    assert detector.calculate_affinity(ctx_tv, doc_tv) == 1.0
    assert detector.calculate_affinity(ctx_tv, doc_phone) <= 0.3
