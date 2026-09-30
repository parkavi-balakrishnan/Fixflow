"""Tests for deterministic variations and end-to-end benchmark metrics."""

import json
from pathlib import Path

from src.engine.benchmark import BenchmarkCase, run_benchmark
from src.engine.pipeline import FixFlowPipeline
from src.engine.variations import QueryVariationGenerator, normalize_query_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_all_official_queries_have_8_to_10_stable_distinct_variations():
    official = json.loads(
        (PROJECT_ROOT / "data" / "siis_responses.json").read_text(encoding="utf-8")
    )["responses"]
    generator = QueryVariationGenerator()

    assert len(official) == 20
    for index, item in enumerate(official, start=1):
        query = item["original_query"]
        variations = generator.generate_variations(query, query_index=index)
        assert 8 <= len(variations) <= 10
        assert variations == generator.generate_variations(query, query_index=index)
        assert all(isinstance(value, str) and value.strip() for value in variations)
        assert len({" ".join(value.lower().split()) for value in variations}) == len(variations)
        assert normalize_query_text(query).lower() not in {
            normalize_query_text(value).lower() for value in variations
        }
        # Canonical-query matching must identify the same curated variation set,
        # including the multiline query with three numbered symptom statements.
        assert variations == generator.generate_variations(query)


def test_rule_based_generator_returns_distinct_variations_for_empty_input():
    variations = QueryVariationGenerator().generate_variations("")

    assert 8 <= len(variations) <= 10
    assert all(variation.strip() for variation in variations)
    assert len({" ".join(variation.lower().split()) for variation in variations}) == len(variations)


def test_benchmark_measures_pipeline_latency_and_telemetry_cache_hits():
    query = json.loads(
        (PROJECT_ROOT / "data" / "siis_responses.json").read_text(encoding="utf-8")
    )["responses"][0]["original_query"]
    pipeline = FixFlowPipeline(prewarm=False)

    report = run_benchmark(
        pipeline,
        [BenchmarkCase(query=query, query_index=1), BenchmarkCase(query=query, query_index=1)],
    )

    assert report.summary["sample_count"] == 2
    assert 0.0 <= report.summary["p50_latency_ms"] <= report.summary["p95_latency_ms"]
    assert report.summary["cache_hit_rate"] == 0.5
    assert report.summary["coverage_rate"] == 1.0
    assert report.summary["schema_validity_rate"] == 1.0
    assert report.summary["url_leakage_rate"] == 0.0
    assert all(result["latency_ms"] >= 0 for result in report.results)
    assert report.results[0]["cache_hit"] is False
    assert report.results[1]["cache_hit"] is True


def test_benchmark_reports_schema_failure_and_url_leakage():
    class PipelineWithInvalidResponse:
        def troubleshoot(self, query):
            return (
                {
                    "contexts": [
                        {
                            "actions": [
                                {"steps": ["Visit https://example.com/help for details."]}
                            ]
                        }
                    ]
                },
                {"cache_hit": True},
            )

    report = run_benchmark(PipelineWithInvalidResponse(), ["test query"])

    assert report.summary["cache_hit_rate"] == 1.0
    assert report.summary["coverage_rate"] == 1.0
    assert report.summary["schema_validity_rate"] == 0.0
    assert report.summary["url_leakage_rate"] == 1.0
    assert report.summary["url_leak_count"] >= 1
    assert report.results[0]["url_leaked"] is True
