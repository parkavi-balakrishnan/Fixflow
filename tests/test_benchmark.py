"""Comprehensive unit and integration tests for FixFlow Benchmark & Evaluation Engine."""
import json
import os
import pytest

from src.engine.benchmark import (
    BenchmarkMetrics,
    BenchmarkReport,
    BenchmarkScenario,
    FixFlowBenchmark,
    ScenarioResult,
    calculate_metrics,
    calculate_percentile,
    compare_benchmark_reports,
    load_canonical_scenarios,
    load_query_variations,
    profile_performance,
)
from src.engine.evaluator import FixFlowEvaluator
from src.schema import Action, ContextDeeplinkResponse, Deeplink, Goal, StepGroup, actionCategory


def test_calculate_percentile_empty_and_valid():
    """Verifies calculate_percentile safely handles empty and populated lists."""
    assert calculate_percentile([], 50) == 0.0
    assert calculate_percentile([], 95) == 0.0

    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert calculate_percentile(vals, 50) == 30.0
    assert calculate_percentile(vals, 95) == 48.0


def test_calculate_metrics_empty():
    """Verifies calculate_metrics handles empty results without ZeroDivisionError."""
    m = calculate_metrics([])
    assert m.total_scenarios == 0
    assert m.passed_scenarios == 0
    assert m.pass_rate == 0.0
    assert m.top1_accuracy == 0.0
    assert m.avg_latency_ms == 0.0


def test_calculate_metrics_correctness():
    """Verifies metric calculations on controlled synthetic scenario results."""
    results = [
        ScenarioResult(
            scenario_id="s1",
            category="canonical",
            query="q1",
            device=None,
            model=None,
            expected_doc_id="doc1",
            retrieved_doc_id="doc1",
            retrieval_method="hybrid",
            retrieval_score=0.9,
            retrieval_latency_ms=2.0,
            total_latency_ms=5.0,
            cache_hit=False,
            response_valid=True,
            schema_valid=True,
            deeplink_valid=True,
            url_leak=False,
            url_leak_count=0,
            retrieval_correct=True,
            top3_correct=True,
            passed=True,
            action_count=2,
        ),
        ScenarioResult(
            scenario_id="s2",
            category="canonical",
            query="q2",
            device=None,
            model=None,
            expected_doc_id="doc2",
            retrieved_doc_id="doc2",
            retrieval_method="cache",
            retrieval_score=1.0,
            retrieval_latency_ms=0.0,
            total_latency_ms=1.0,
            cache_hit=True,
            response_valid=True,
            schema_valid=True,
            deeplink_valid=True,
            url_leak=False,
            url_leak_count=0,
            retrieval_correct=True,
            top3_correct=True,
            passed=True,
            action_count=2,
        ),
        ScenarioResult(
            scenario_id="s3",
            category="paraphrased",
            query="q3",
            device=None,
            model=None,
            expected_doc_id="doc3",
            retrieved_doc_id="wrong_doc",
            retrieval_method="hybrid",
            retrieval_score=0.4,
            retrieval_latency_ms=3.0,
            total_latency_ms=10.0,
            cache_hit=False,
            response_valid=True,
            schema_valid=True,
            deeplink_valid=True,
            url_leak=True,
            url_leak_count=1,
            retrieval_correct=False,
            top3_correct=False,
            passed=False,
            action_count=1,
        ),
    ]

    m = calculate_metrics(results)
    assert m.total_scenarios == 3
    assert m.passed_scenarios == 2
    assert m.failed_scenarios == 1
    assert round(m.pass_rate, 2) == 0.67
    assert round(m.top1_accuracy, 2) == 0.67
    assert m.exact_query_accuracy == 1.0
    assert m.paraphrased_query_accuracy == 0.0
    assert m.schema_validity_rate == 1.0
    assert m.url_leak_count == 1
    assert round(m.cache_hit_rate, 2) == 0.33
    assert m.p50_latency_ms == 5.0


def test_load_canonical_scenarios():
    """Verifies loading the 20 official scenarios from data/input.txt."""
    scenarios = load_canonical_scenarios()
    assert len(scenarios) == 20
    assert scenarios[0].scenario_id == "canonical_01"
    assert scenarios[0].category == "canonical"
    assert scenarios[0].expected_doc_id == "row_1"
    assert scenarios[-1].scenario_id == "canonical_20"
    assert scenarios[-1].expected_doc_id == "row_22"


def test_load_query_variations_deterministic():
    """Verifies that query variation suite covers all required categories deterministically."""
    vars1 = load_query_variations()
    vars2 = load_query_variations()

    assert len(vars1) == len(vars2)
    categories = {s.category for s in vars1}
    assert "canonical" in categories
    assert "paraphrased" in categories
    assert "vague" in categories
    assert "device_specific" in categories
    assert "unrelated" in categories
    assert "edge_case" in categories
    assert len(vars1) >= 40


def test_benchmark_scenario_evaluation_pass():
    """Verifies that an authentic scenario evaluates as passed with complete telemetry."""
    bm = FixFlowBenchmark()
    sc = BenchmarkScenario(
        scenario_id="test_01",
        query="The mobile phone screen is cracked and flashes intermittently.",
        category="canonical",
        expected_doc_id="row_14",
    )
    res = bm.evaluate_scenario(sc)

    assert res.scenario_id == "test_01"
    assert res.schema_valid is True
    assert res.deeplink_valid is True
    assert res.url_leak is False
    assert res.url_leak_count == 0
    assert res.passed is True
    assert res.total_latency_ms > 0.0
    assert res.action_count > 0


def test_benchmark_scenario_evaluation_url_leak():
    """Verifies that URL leakage is detected by the benchmark and causes failure."""
    bm = FixFlowBenchmark()
    leaking_resp = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Display Troubleshooting",
                title="Display issue",
                score=0.9,
                actions=[
                    Action(
                        actionName="Test Action",
                        description="It will help resolve device settings",
                        stepGroups=[
                            StepGroup(
                                steps=[
                                    "Open settings.",
                                    "Visit https://samsung.com/support for more info.",
                                ],
                                actionableDeeplink=Deeplink(
                                    deeplink="bixby://dummy_positive",
                                    description="Safe fallback",
                                ),
                            )
                        ],
                        category=actionCategory.auto,
                    )
                ],
            )
        ]
    )

    class MockLeakingPipeline:
        def troubleshoot(self, *args, **kwargs):
            return leaking_resp, {"cache_hit": False, "latency_ms": 1.0}

    bm.pipeline = MockLeakingPipeline()
    sc = BenchmarkScenario(
        scenario_id="test_leak",
        query="Phone screen broken",
    )
    res = bm.evaluate_scenario(sc)
    assert res.url_leak is True
    assert res.url_leak_count > 0
    assert res.passed is False


def test_benchmark_scenario_evaluation_malformed_pipeline():
    """Verifies that benchmark handles pipeline exceptions cleanly without crashing."""
    class CrashingPipeline:
        def troubleshoot(self, *args, **kwargs):
            raise RuntimeError("Simulated internal pipeline crash")

    bm = FixFlowBenchmark(pipeline=CrashingPipeline())
    sc = BenchmarkScenario(scenario_id="test_crash", query="Crashing query")
    res = bm.evaluate_scenario(sc)

    assert res.passed is False
    assert res.schema_valid is False
    assert res.error == "Simulated internal pipeline crash"


def test_benchmark_deeplink_validation_failure():
    """Verifies that hallucinated or non-catalog deeplinks fail deeplink validation."""
    bm = FixFlowBenchmark()
    # Construct synthetic response with an invented URI
    malformed_resp = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Display Troubleshooting",
                title="Display issue",
                score=0.9,
                actions=[
                    Action(
                        actionName="Test Action",
                        description="It will help resolve device settings",
                        stepGroups=[
                            StepGroup(
                                steps=["Open settings"],
                                actionableDeeplink=Deeplink(
                                    deeplink="bixby://invented/fake/path",
                                    description="Fake link",
                                    message="Fake",
                                ),
                            )
                        ],
                        category=actionCategory.auto,
                    )
                ],
            )
        ]
    )

    class MockPipeline:
        def troubleshoot(self, *args, **kwargs):
            return malformed_resp, {"cache_hit": False, "latency_ms": 1.0}

    bm.pipeline = MockPipeline()
    sc = BenchmarkScenario(scenario_id="test_bad_dl", query="Any query")
    res = bm.evaluate_scenario(sc)

    assert res.deeplink_valid is False
    assert res.passed is False


def test_benchmark_cold_vs_warm_cache_measurement():
    """Verifies cache hit transitions between cold pass and repeat pass."""
    bm = FixFlowBenchmark()
    canonical = load_canonical_scenarios()[:3]

    # Cold run
    rep_cold = bm.run(scenarios=canonical, mode="cold", repeat_for_cache=False)
    for r in rep_cold.results:
        assert r.cache_hit is False

    # Warm run
    rep_warm = bm.run(scenarios=canonical, mode="warm", repeat_for_cache=False)
    for r in rep_warm.results:
        assert r.cache_hit is True


def test_benchmark_results_jsonl_generation(tmp_path):
    """Verifies results.jsonl output format matches schema requirements."""
    bm = FixFlowBenchmark()
    canonical = load_canonical_scenarios()[:2]
    rep = bm.run(scenarios=canonical, mode="cold", repeat_for_cache=False)

    out_file = tmp_path / "results.jsonl"
    bm.save_results_jsonl(rep, str(out_file))

    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f]

    assert len(lines) == 2
    for item in lines:
        assert "scenario_id" in item
        assert "query" in item
        assert "retrieved_doc_id" in item
        assert "retrieval_score" in item
        assert "retrieval_latency_ms" in item
        assert "total_latency_ms" in item
        assert "cache_hit" in item
        assert "schema_valid" in item
        assert "deeplink_valid" in item
        assert "url_leak" in item
        assert "passed" in item


def test_benchmark_reports_json_and_markdown(tmp_path):
    """Verifies benchmark report JSON and Markdown file generation."""
    bm = FixFlowBenchmark()
    canonical = load_canonical_scenarios()[:2]
    rep = bm.run(scenarios=canonical, mode="cold", repeat_for_cache=False)

    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    bm.save_report_json(rep, str(json_path))
    md_content = bm.save_report_md(rep, str(md_path))

    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "metrics" in data
    assert "results" in data

    assert "# FixFlow Benchmark & Evaluation Report" in md_content
    assert "Executive Summary" in md_content


def test_compare_benchmark_reports():
    """Verifies comparing baseline and current reports correctly identifies deltas."""
    baseline = {
        "metrics": {
            "top1_accuracy": 0.85,
            "top3_accuracy": 0.90,
            "avg_latency_ms": 15.0,
            "p95_latency_ms": 50.0,
            "failed_scenarios": 2,
        }
    }
    current = {
        "metrics": {
            "top1_accuracy": 1.00,
            "top3_accuracy": 1.00,
            "avg_latency_ms": 5.0,
            "p95_latency_ms": 20.0,
            "failed_scenarios": 0,
        }
    }
    comparison = compare_benchmark_reports(baseline, current)
    assert comparison["summary"]["improved"] >= 3
    assert comparison["summary"]["regressed"] == 0
    assert comparison["summary"]["verdict"] == "improved"
    assert comparison["metrics"]["top1_accuracy"]["status"] == "improved"
    assert comparison["metrics"]["avg_latency_ms"]["status"] == "improved"


def test_profile_performance():
    """Verifies performance profiling returns valid measurements across dimensions."""
    perf = profile_performance()
    assert perf["cold_start_seconds"] > 0.0
    assert perf["deeplink_catalog_load_ms"] > 0.0
    assert "avg_ms" in perf["cache_hit"]
    assert "p95_ms" in perf["cache_hit"]
    assert "avg_ms" in perf["cache_miss"]
    assert "throughput_req_per_sec" in perf["concurrency"]


def test_evaluator_audit_and_gates():
    """Verifies evaluator audits official scripts and evaluates G2-G5 and A1-A5."""
    evaluator = FixFlowEvaluator()
    report = evaluator.evaluate_all()

    # Audit check
    assert "eval_submission.py" in report.official_evaluator_files_found
    assert "scorer.py" in report.official_evaluator_files_found

    # Gate checks
    for gid in ["G2", "G3", "G4", "G5", "A1", "A2", "A3", "A4", "A5"]:
        assert gid in report.gates
        assert report.gates[gid].status == "PASS"

    assert report.overall_status == "PASS"
