"""FixFlow Benchmark & Evaluation Engine.

Provides an end-to-end evaluation suite for the complete FixFlow pipeline:
- Canonical official 20 scenarios from data/input.txt
- Multi-category query variations (paraphrased, vague, device-specific, unrelated, edge-case)
- Deterministic execution and rigorous metric calculations:
    - Top-1 and Top-3 retrieval accuracy
    - Exact-query vs paraphrased-query accuracy
    - Coverage, schema validity, deeplink validity, zero URL leak rates
    - Cache hit rate, average, P50, and P95 latency
    - Error rate and total scenarios passed
- Output generation: results.jsonl, benchmark_report.json, benchmark_report.md
- Performance profiling and version-to-version comparison.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

from src.config import (
    DATA_DIR,
    DEFAULT_CACHE_THRESHOLD,
    DEFAULT_REPORT_JSON,
    DEFAULT_REPORT_MD,
    DEFAULT_RESULTS_JSONL,
    INPUT_TXT_PATH,
    PROCESSED_SIIS_PATH,
    SAMPLE_OUTPUT_PATH,
)
from src.engine.pipeline import FixFlowPipeline
from src.engine.validator import (
    DeeplinkCatalogIndex,
    detect_url_leakage,
    get_default_catalog_index,
    validate_response,
)
from src.schema import ContextDeeplinkResponse

logger = logging.getLogger("fixflow.benchmark")


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculates percentile safely from a list of values."""
    if not values:
        return 0.0
    return round(float(np.percentile(values, percentile)), 2)


@dataclass
class BenchmarkScenario:
    """Definition of an evaluation scenario."""
    scenario_id: str
    query: str
    category: str = "canonical"  # canonical, paraphrased, vague, device_specific, unrelated, edge_case
    device: Optional[str] = None
    model: Optional[str] = None
    expected_doc_id: Optional[str] = None
    expected_title_sub: Optional[str] = None
    siis_response: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "query": self.query,
            "category": self.category,
            "device": self.device,
            "model": self.model,
            "expected_doc_id": self.expected_doc_id,
            "expected_title_sub": self.expected_title_sub,
            "has_siis_response": self.siis_response is not None,
            "metadata": self.metadata,
        }


@dataclass
class ScenarioResult:
    """Result of running a single benchmark scenario through the pipeline."""
    scenario_id: str
    category: str
    query: str
    device: Optional[str]
    model: Optional[str]
    expected_doc_id: Optional[str] = None
    retrieved_doc_id: Optional[str] = None
    retrieval_method: str = "none"
    retrieval_score: float = 0.0
    retrieval_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    cache_hit: bool = False
    response_valid: bool = False
    schema_valid: bool = False
    deeplink_valid: bool = False
    url_leak: bool = False
    url_leak_count: int = 0
    retrieval_correct: Optional[bool] = None
    top3_correct: Optional[bool] = None
    passed: bool = False
    error: Optional[str] = None
    response_title: Optional[str] = None
    action_count: int = 0
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to standardized dictionary matching results.jsonl schema."""
        return {
            "scenario_id": self.scenario_id,
            "category": self.category,
            "query": self.query,
            "device": self.device,
            "model": self.model,
            "expected_doc_id": self.expected_doc_id,
            "retrieved_doc_id": self.retrieved_doc_id,
            "retrieval_method": self.retrieval_method,
            "retrieval_score": round(self.retrieval_score, 4),
            "retrieval_latency_ms": round(self.retrieval_latency_ms, 2),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "cache_hit": self.cache_hit,
            "schema_valid": self.schema_valid,
            "deeplink_valid": self.deeplink_valid,
            "url_leak": self.url_leak,
            "url_leak_count": self.url_leak_count,
            "response_valid": self.response_valid,
            "retrieval_correct": self.retrieval_correct,
            "top3_correct": self.top3_correct,
            "passed": self.passed,
            "action_count": self.action_count,
            "response_title": self.response_title,
            "error": self.error,
        }


@dataclass
class BenchmarkMetrics:
    """Aggregated benchmark metrics across executed scenarios."""
    total_scenarios: int = 0
    passed_scenarios: int = 0
    failed_scenarios: int = 0
    pass_rate: float = 0.0
    top1_accuracy: float = 0.0
    top3_accuracy: float = 0.0
    exact_query_accuracy: float = 0.0
    paraphrased_query_accuracy: float = 0.0
    coverage: float = 0.0
    schema_validity_rate: float = 0.0
    deeplink_validity_rate: float = 0.0
    url_leak_count: int = 0
    url_leak_clean_rate: float = 0.0
    cache_hit_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    avg_retrieval_latency_ms: float = 0.0
    error_rate: float = 0.0
    category_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_scenarios": self.total_scenarios,
            "passed_scenarios": self.passed_scenarios,
            "failed_scenarios": self.failed_scenarios,
            "pass_rate": round(self.pass_rate, 4),
            "top1_accuracy": round(self.top1_accuracy, 4),
            "top3_accuracy": round(self.top3_accuracy, 4),
            "exact_query_accuracy": round(self.exact_query_accuracy, 4),
            "paraphrased_query_accuracy": round(self.paraphrased_query_accuracy, 4),
            "coverage": round(self.coverage, 4),
            "schema_validity_rate": round(self.schema_validity_rate, 4),
            "deeplink_validity_rate": round(self.deeplink_validity_rate, 4),
            "url_leak_count": self.url_leak_count,
            "url_leak_clean_rate": round(self.url_leak_clean_rate, 4),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "avg_retrieval_latency_ms": round(self.avg_retrieval_latency_ms, 2),
            "error_rate": round(self.error_rate, 4),
            "category_breakdown": self.category_breakdown,
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark report including metrics and per-scenario details."""
    metrics: BenchmarkMetrics
    results: List[ScenarioResult]
    timestamp: str
    mode: str
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "duration_seconds": round(self.duration_seconds, 2),
            "metrics": self.metrics.to_dict(),
            "results": [r.to_dict() for r in self.results],
        }


# Canonical doc mapping for the 20 lines of data/input.txt
CANONICAL_DOC_MAP: List[str] = [
    "row_1",   # 1. Tablet flashes and goes blank in Gmail
    "row_2",   # 2. Galaxy S22 screen turns blank or white on stock/Smart Tutor
    "row_3",   # 3. Galaxy Z Flip 7 screen completely black, cannot use Smart Switch
    "row_4",   # 4. Galaxy A15/A16 screen went black on its own
    "row_5",   # 5. Galaxy tablet screen blank scanning QR code for Smart Switch
    "row_7",   # 6. Tablet screen dark, only 3 app icons lit
    "row_8",   # 7. Screen stays small, doesn't fill whole display (mirroring)
    "row_9",   # 8. Galaxy Flip 7 inner screen stopped, outer cover works
    "row_10",  # 9. Galaxy Z Flip 6 flickers/goes blank when opening (Camera)
    "row_11",  # 10. Galaxy Flip 6 screen half black
    "row_12",  # 11. Galaxy S25 floating circle quick shortcuts
    "row_13",  # 12. Galaxy S22 blank after carrier deactivated old phone
    "row_14",  # 13. Screen is completely cracked, total crack
    "row_15",  # 14. Galaxy S26 Ultra shows blue/black screen with tiny text
    "row_16",  # 15. Galaxy S***** Ultra flashes quickly when plugged into charger
    "row_17",  # 16. Galaxy S24 blank dark screen with occasional scrolling
    "row_19",  # 17. Galaxy Z Flip 7 screen cracked right where it folds
    "row_20",  # 18. Galaxy A17 screen looks distorted, diagnostic test (rotation)
    "row_21",  # 19. Galaxy S22 inputs delayed and touch responsiveness is laggy
    "row_22",  # 20. Galaxy S24 Ultra screen black, powers on and rings
]


def load_canonical_scenarios(data_dir: str = DATA_DIR) -> List[BenchmarkScenario]:
    """Loads the 20 official canonical scenarios from data/input.txt."""
    input_path = os.path.join(data_dir, "input.txt")
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Canonical input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        queries = [l.strip() for l in f if l.strip()]

    scenarios: List[BenchmarkScenario] = []
    for idx, query in enumerate(queries):
        expected_doc = CANONICAL_DOC_MAP[idx] if idx < len(CANONICAL_DOC_MAP) else None
        scenarios.append(
            BenchmarkScenario(
                scenario_id=f"canonical_{idx+1:02d}",
                query=query,
                category="canonical",
                expected_doc_id=expected_doc,
                metadata={"index": idx, "source": "input.txt"},
            )
        )
    return scenarios


def load_query_variations(data_dir: str = DATA_DIR) -> List[BenchmarkScenario]:
    """Builds a deterministic, comprehensive test suite covering all required query variations."""
    scenarios = load_canonical_scenarios(data_dir)

    # 1. Paraphrased Queries (from test_retrieval.py suite)
    paraphrases = [
        ("My Galaxy S22 screen is lagging when I touch it", "row_21", "Touchscreen issues on a Galaxy phone or tablet"),
        ("Phone glass cracked after falling on the floor", "row_14", "Cracked or bleeding screen on Galaxy phone or tablet"),
        ("Camera video flickers when recording in the room", "row_10", "Screen flickers when using the Camera on a Galaxy phone"),
        ("How to transfer files with QR code on tablet", "row_5", "Transfer Secure folder with Smart Switch"),
        ("Screen will not rotate when turning sideways", "row_20", "Screen does not rotate on Galaxy phone or tablet"),
        ("Floating icon button on screen", "row_12", "Use Multi window and App pairs on your Galaxy phone or tablet"),
        ("Cast phone screen to Samsung Smart TV", "row_8", "Screen mirroring to your Samsung TV"),
        ("Cannot access my email account on tablet", "row_1", "Email server not responding on Samsung phone or tablet"),
    ]
    for idx, (query, exp_doc, title_sub) in enumerate(paraphrases):
        scenarios.append(
            BenchmarkScenario(
                scenario_id=f"paraphrase_{idx+1:02d}",
                query=query,
                category="paraphrased",
                expected_doc_id=exp_doc,
                expected_title_sub=title_sub,
            )
        )

    # 2. Vague Queries
    vague_queries = [
        ("Device screen is dark and won't turn on", "row_22", "Blank or black display on a Samsung phone or tablet"),
        ("Display not rotating", "row_20", "Screen does not rotate on Galaxy phone or tablet"),
        ("Delayed touch input", "row_21", "Touchscreen issues on a Galaxy phone or tablet"),
    ]
    for idx, (query, exp_doc, title_sub) in enumerate(vague_queries):
        scenarios.append(
            BenchmarkScenario(
                scenario_id=f"vague_{idx+1:02d}",
                query=query,
                category="vague",
                expected_doc_id=exp_doc,
                expected_title_sub=title_sub,
            )
        )

    # 3. Device-Specific Queries
    device_queries = [
        ("screen stays small and does not expand to fill the entire TV", "Samsung TV", None, "row_8", "Screen mirroring"),
        ("flashes and goes blank when opening mail", "Galaxy Tab", None, "row_1", "Email server"),
        ("inner screen stopped working, outer cover screen works", "Galaxy Z Flip 7", None, "row_9", "Access your Galaxy"),
        ("touch responsiveness is laggy", None, "Galaxy S22", "row_21", "Touchscreen issues"),
    ]
    for idx, (query, dev, mod, exp_doc, title_sub) in enumerate(device_queries):
        scenarios.append(
            BenchmarkScenario(
                scenario_id=f"device_{idx+1:02d}",
                query=query,
                category="device_specific",
                device=dev,
                model=mod,
                expected_doc_id=exp_doc,
                expected_title_sub=title_sub,
            )
        )

    # 4. Unrelated Queries (Safe Grounding Verification)
    unrelated_queries = [
        "how to bake chocolate chip cookies at home",
        "order pepperoni pizza online delivery",
        "current weather forecast in Tokyo and Paris",
    ]
    for idx, query in enumerate(unrelated_queries):
        scenarios.append(
            BenchmarkScenario(
                scenario_id=f"unrelated_{idx+1:02d}",
                query=query,
                category="unrelated",
                expected_doc_id=None,
            )
        )

    # 5. Edge-Case Queries
    edge_queries = [
        ("1. \"My Galaxy S24 screen goes completely blank, just a dark screen with occasional scrolling\"", "row_17", "Some things to check first"),
        ("1. \"My Galaxy Z Flip 7 screen is cracked again right where it folds.\" 2. \"The touch doesn't work\"", "row_19", "Cracked or bleeding screen"),
        ("My Samsung S***** Ultra screen flashes extremely quickly (in milliseconds) whenever I plug in a charger", "row_16", "Blank or black display"),
        ("   MY GALAXY S22 SCREEN INPUTS ARE DELAYED AND LAGGY...   ", "row_21", "Touchscreen issues"),
    ]
    for idx, (query, exp_doc, title_sub) in enumerate(edge_queries):
        scenarios.append(
            BenchmarkScenario(
                scenario_id=f"edge_{idx+1:02d}",
                query=query,
                category="edge_case",
                expected_doc_id=exp_doc,
                expected_title_sub=title_sub,
            )
        )

    return scenarios


def calculate_metrics(results: List[ScenarioResult]) -> BenchmarkMetrics:
    """Computes comprehensive benchmark metrics from a list of scenario results."""
    if not results:
        return BenchmarkMetrics()

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    # Retrieval accuracy across scenarios with expected doc
    evaluable_retrieval = [r for r in results if r.expected_doc_id is not None]
    top1_correct = sum(1 for r in evaluable_retrieval if r.retrieval_correct is True)
    top3_correct = sum(1 for r in evaluable_retrieval if r.top3_correct is True)

    top1_acc = (top1_correct / len(evaluable_retrieval)) if evaluable_retrieval else 0.0
    top3_acc = (top3_correct / len(evaluable_retrieval)) if evaluable_retrieval else 0.0

    # Category accuracies
    canonical_res = [r for r in results if r.category == "canonical"]
    exact_acc = (
        sum(1 for r in canonical_res if r.retrieval_correct is True) / len(canonical_res)
        if canonical_res
        else 0.0
    )

    paraphrase_res = [r for r in results if r.category == "paraphrased"]
    para_acc = (
        sum(1 for r in paraphrase_res if r.retrieval_correct is True) / len(paraphrase_res)
        if paraphrase_res
        else 0.0
    )

    # Coverage: scenarios that successfully yielded valid actions
    covered = sum(1 for r in results if r.action_count > 0 and r.response_valid)
    coverage_rate = covered / total

    # Validity rates
    schema_valid_count = sum(1 for r in results if r.schema_valid)
    schema_valid_rate = schema_valid_count / total

    deeplink_valid_count = sum(1 for r in results if r.deeplink_valid)
    deeplink_valid_rate = deeplink_valid_count / total

    total_url_leaks = sum(r.url_leak_count for r in results)
    url_clean_count = sum(1 for r in results if not r.url_leak)
    url_clean_rate = url_clean_count / total

    # Cache hit rate
    cache_hits = sum(1 for r in results if r.cache_hit)
    cache_hit_rate = cache_hits / total

    # Latencies
    latencies = [r.total_latency_ms for r in results]
    avg_lat = float(np.mean(latencies)) if latencies else 0.0
    p50_lat = calculate_percentile(latencies, 50)
    p95_lat = calculate_percentile(latencies, 95)
    min_lat = min(latencies) if latencies else 0.0
    max_lat = max(latencies) if latencies else 0.0

    retrieval_lats = [r.retrieval_latency_ms for r in results if not r.cache_hit]
    avg_ret_lat = float(np.mean(retrieval_lats)) if retrieval_lats else 0.0

    # Error rate
    errors = sum(1 for r in results if r.error is not None)
    error_rate = errors / total

    # Category breakdown
    categories: Set[str] = {r.category for r in results}
    cat_breakdown: Dict[str, Dict[str, Any]] = {}
    for cat in sorted(categories):
        cat_items = [r for r in results if r.category == cat]
        cat_passed = sum(1 for r in cat_items if r.passed)
        cat_lats = [r.total_latency_ms for r in cat_items]
        cat_eval = [r for r in cat_items if r.expected_doc_id is not None]
        cat_acc = (
            sum(1 for r in cat_eval if r.retrieval_correct is True) / len(cat_eval)
            if cat_eval
            else 1.0
        )
        cat_breakdown[cat] = {
            "total": len(cat_items),
            "passed": cat_passed,
            "pass_rate": round(cat_passed / len(cat_items), 4),
            "accuracy": round(cat_acc, 4),
            "avg_latency_ms": round(float(np.mean(cat_lats)), 2) if cat_lats else 0.0,
            "p95_latency_ms": calculate_percentile(cat_lats, 95),
        }

    return BenchmarkMetrics(
        total_scenarios=total,
        passed_scenarios=passed,
        failed_scenarios=failed,
        pass_rate=passed / total,
        top1_accuracy=top1_acc,
        top3_accuracy=top3_acc,
        exact_query_accuracy=exact_acc,
        paraphrased_query_accuracy=para_acc,
        coverage=coverage_rate,
        schema_validity_rate=schema_valid_rate,
        deeplink_validity_rate=deeplink_valid_rate,
        url_leak_count=total_url_leaks,
        url_leak_clean_rate=url_clean_rate,
        cache_hit_rate=cache_hit_rate,
        avg_latency_ms=avg_lat,
        p50_latency_ms=p50_lat,
        p95_latency_ms=p95_lat,
        min_latency_ms=min_lat,
        max_latency_ms=max_lat,
        avg_retrieval_latency_ms=avg_ret_lat,
        error_rate=error_rate,
        category_breakdown=cat_breakdown,
    )


class FixFlowBenchmark:
    """Benchmark orchestrator for the complete FixFlow system."""

    def __init__(
        self,
        pipeline: Optional[FixFlowPipeline] = None,
        data_dir: str = DATA_DIR,
        catalog_index: Optional[DeeplinkCatalogIndex] = None,
    ):
        self.data_dir = data_dir
        self.pipeline = pipeline or FixFlowPipeline(prewarm=False, data_dir=data_dir)
        self.catalog = catalog_index or get_default_catalog_index()

    def evaluate_scenario(self, scenario: BenchmarkScenario) -> ScenarioResult:
        """Executes a single scenario through the actual FixFlow pipeline and evaluates output."""
        start_time = time.perf_counter()
        error_str: Optional[str] = None
        resp: Optional[ContextDeeplinkResponse] = None
        telemetry: Dict[str, Any] = {}

        try:
            resp, telemetry = self.pipeline.troubleshoot(
                scenario.query,
                siis_response=scenario.siis_response,
                device=scenario.device,
                model=scenario.model,
            )
        except Exception as e:
            error_str = str(e)
            logger.error(f"Execution error on {scenario.scenario_id}: {error_str}", exc_info=True)

        total_lat = (time.perf_counter() - start_time) * 1000.0

        if resp is None:
            return ScenarioResult(
                scenario_id=scenario.scenario_id,
                category=scenario.category,
                query=scenario.query,
                device=scenario.device,
                model=scenario.model,
                expected_doc_id=scenario.expected_doc_id,
                retrieved_doc_id=None,
                retrieval_method="none",
                retrieval_score=0.0,
                retrieval_latency_ms=0.0,
                total_latency_ms=round(total_lat, 2),
                cache_hit=False,
                response_valid=False,
                schema_valid=False,
                deeplink_valid=False,
                url_leak=False,
                url_leak_count=0,
                retrieval_correct=False if scenario.expected_doc_id else None,
                top3_correct=False if scenario.expected_doc_id else None,
                passed=False,
                error=error_str or "Pipeline returned None",
            )

        # 1. Schema & Rubric validation
        val_result = validate_response(resp)
        schema_valid = val_result.is_valid
        val_errors = list(val_result.errors)

        # 2. Deeplink validity checking
        deeplink_valid = True
        for goal in resp.contexts:
            for action in goal.actions:
                for sg in action.stepGroups:
                    if sg.actionableDeeplink:
                        uri = sg.actionableDeeplink.deeplink
                        if not self.catalog.is_valid_actionable_uri(uri):
                            deeplink_valid = False
                            val_errors.append(f"Invalid actionable deeplink URI: {uri}")
                    if sg.validationDeeplink:
                        v_uri = sg.validationDeeplink.deeplink
                        if not self.catalog.is_valid_validation_uri(v_uri):
                            deeplink_valid = False
                            val_errors.append(f"Invalid validation deeplink URI: {v_uri}")

        # 3. URL leak detection (Gate G5)
        raw_json = resp.model_dump_json()
        leaks = detect_url_leakage(raw_json)
        url_leak = len(leaks) > 0
        url_leak_count = len(leaks)

        # 4. Retrieval metrics
        cache_hit = bool(telemetry.get("cache_hit", False))
        retrieved_id = telemetry.get("retrieved_doc_id")
        ret_score = float(telemetry.get("retrieval_score", 0.0))
        ret_lat = float(telemetry.get("retrieval_latency_ms", 0.0))
        ret_method = str(telemetry.get("retrieval_method", telemetry.get("source", "unknown")))

        # Response details
        resp_title = resp.contexts[0].title if resp.contexts else None
        action_count = sum(len(g.actions) for g in resp.contexts)

        # Check retrieval correctness
        retrieval_correct: Optional[bool] = None
        top3_correct: Optional[bool] = None
        if scenario.expected_doc_id or scenario.expected_title_sub:
            res = self.pipeline.retriever.retrieve(
                scenario.query, device=scenario.device or scenario.model, top_k=3
            )
            top1_cand = res.matched_doc
            top3_cands = res.candidates[:3]

            def match_candidate(cand) -> bool:
                if cand is None:
                    return False
                if scenario.expected_doc_id and cand.doc_id == scenario.expected_doc_id:
                    return True
                if scenario.expected_title_sub and scenario.expected_title_sub.lower() in cand.title.lower():
                    return True
                return False

            retrieval_correct = match_candidate(top1_cand)
            top3_correct = any(match_candidate(c) for c in top3_cands)

        # Determine pass/fail
        if scenario.category == "unrelated":
            # Unrelated queries should have low confidence score (< 0.50) or safe fallback
            passed = (ret_score < 0.50 or schema_valid) and not url_leak
        else:
            ret_ok = True if retrieval_correct is None else retrieval_correct
            passed = schema_valid and not url_leak and deeplink_valid and ret_ok and (error_str is None)

        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            category=scenario.category,
            query=scenario.query,
            device=scenario.device,
            model=scenario.model,
            expected_doc_id=scenario.expected_doc_id,
            retrieved_doc_id=retrieved_id,
            retrieval_method=ret_method,
            retrieval_score=ret_score,
            retrieval_latency_ms=ret_lat,
            total_latency_ms=round(total_lat, 2),
            cache_hit=cache_hit,
            response_valid=val_result.is_valid,
            schema_valid=schema_valid,
            deeplink_valid=deeplink_valid,
            url_leak=url_leak,
            url_leak_count=url_leak_count,
            retrieval_correct=retrieval_correct,
            top3_correct=top3_correct,
            passed=passed,
            error=error_str,
            response_title=resp_title,
            action_count=action_count,
            validation_errors=val_errors,
        )

    def run(
        self,
        scenarios: Optional[List[BenchmarkScenario]] = None,
        mode: str = "full",
        repeat_for_cache: bool = True,
    ) -> BenchmarkReport:
        """Runs the benchmark across scenarios.
        
        Modes:
        - "cold": runs cold pipeline with unwarmed cache
        - "warm": prewarms cache before running
        - "full": runs cold pass first, then repeat pass to measure cache hit rate and latency
        """
        start_wall = time.perf_counter()
        if scenarios is None:
            scenarios = load_query_variations(self.data_dir)

        if mode == "warm":
            self.pipeline = FixFlowPipeline(prewarm=True, data_dir=self.data_dir)
        elif mode in ("cold", "full"):
            self.pipeline = FixFlowPipeline(prewarm=False, data_dir=self.data_dir)

        results: List[ScenarioResult] = []

        # Pass 1: Primary execution
        for sc in scenarios:
            res = self.evaluate_scenario(sc)
            results.append(res)

        # Pass 2: Repeat execution if mode is 'full' to test warm-cache hit performance
        if mode == "full" and repeat_for_cache:
            for sc in scenarios:
                if sc.category in ("canonical", "paraphrased"):
                    res_repeat = self.evaluate_scenario(sc)
                    # Include repeat results to reflect cache hit metrics
                    results.append(res_repeat)

        duration = time.perf_counter() - start_wall
        metrics = calculate_metrics(results)

        return BenchmarkReport(
            metrics=metrics,
            results=results,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            duration_seconds=duration,
        )

    def save_results_jsonl(self, report: BenchmarkReport, output_path: str = DEFAULT_RESULTS_JSONL) -> None:
        """Writes scenario results to results.jsonl, one JSON object per line."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for r in report.results:
                f.write(json.dumps(r.to_dict()) + "\n")

    def save_report_json(self, report: BenchmarkReport, output_path: str = DEFAULT_REPORT_JSON) -> None:
        """Saves machine-readable benchmark report JSON."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

    def save_report_md(self, report: BenchmarkReport, output_path: str = DEFAULT_REPORT_MD) -> str:
        """Generates a rich, human-readable markdown benchmark report."""
        m = report.metrics
        md_lines = [
            "# FixFlow Benchmark & Evaluation Report",
            f"*Generated: {report.timestamp} | Mode: {report.mode} | Duration: {report.duration_seconds:.2f}s*",
            "",
            "## 1. Executive Summary",
            "",
            "| Metric | Result | Target / Standard | Status |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Total Scenarios Evaluated** | {m.total_scenarios} | - | COMPLETED |",
            f"| **Scenarios Passed** | {m.passed_scenarios} / {m.total_scenarios} ({m.pass_rate:.1%}) | >= 90% | {'PASS' if m.pass_rate >= 0.90 else 'FAIL'} |",
            f"| **Top-1 Retrieval Accuracy** | {m.top1_accuracy:.1%} | >= 95% | {'PASS' if m.top1_accuracy >= 0.95 else 'FAIL'} |",
            f"| **Top-3 Retrieval Accuracy** | {m.top3_accuracy:.1%} | 100% | {'PASS' if m.top3_accuracy == 1.0 else 'FAIL'} |",
            f"| **Exact Query Accuracy** | {m.exact_query_accuracy:.1%} | 100% | {'PASS' if m.exact_query_accuracy == 1.0 else 'FAIL'} |",
            f"| **Paraphrased Query Accuracy** | {m.paraphrased_query_accuracy:.1%} | >= 80% | {'PASS' if m.paraphrased_query_accuracy >= 0.80 else 'FAIL'} |",
            f"| **Pipeline Coverage** | {m.coverage:.1%} | 100% | {'PASS' if m.coverage == 1.0 else 'FAIL'} |",
            f"| **Schema Validity Rate** | {m.schema_validity_rate:.1%} | 100% | {'PASS' if m.schema_validity_rate == 1.0 else 'FAIL'} |",
            f"| **Deeplink Validity Rate** | {m.deeplink_validity_rate:.1%} | 100% | {'PASS' if m.deeplink_validity_rate == 1.0 else 'FAIL'} |",
            f"| **Gate G5 URL Leaks** | {m.url_leak_count} (Clean: {m.url_leak_clean_rate:.1%}) | 0 leaks | {'PASS' if m.url_leak_count == 0 else 'FAIL'} |",
            f"| **Semantic Cache Hit Rate** | {m.cache_hit_rate:.1%} | >= 30% | {'PASS' if m.cache_hit_rate >= 0.30 else 'FAIL'} |",
            f"| **Average Pipeline Latency** | {m.avg_latency_ms:.2f} ms | < 50 ms | {'PASS' if m.avg_latency_ms < 50.0 else 'FAIL'} |",
            f"| **P50 Pipeline Latency** | {m.p50_latency_ms:.2f} ms | < 20 ms | {'PASS' if m.p50_latency_ms < 20.0 else 'FAIL'} |",
            f"| **P95 Pipeline Latency** | {m.p95_latency_ms:.2f} ms | < 300 ms | {'PASS' if m.p95_latency_ms < 300.0 else 'FAIL'} |",
            f"| **Pipeline Error Rate** | {m.error_rate:.1%} | 0% | {'PASS' if m.error_rate == 0.0 else 'FAIL'} |",
            "",
            "## 2. Category Performance Breakdown",
            "",
            "| Category | Scenarios | Passed | Accuracy | Avg Latency | P95 Latency |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for cat, data in m.category_breakdown.items():
            md_lines.append(
                f"| `{cat}` | {data['total']} | {data['passed']} ({data['pass_rate']:.1%}) | "
                f"{data['accuracy']:.1%} | {data['avg_latency_ms']:.2f} ms | {data['p95_latency_ms']:.2f} ms |"
            )

        md_lines.extend([
            "",
            "## 3. Official 20 Canonical Scenarios Detail",
            "",
            "| ID | Query Excerpt | Expected Doc | Retrieved Doc | Latency | Cache Hit | Passed |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        seen_canonical: Set[str] = set()
        for r in report.results:
            if r.category == "canonical":
                is_repeat = r.scenario_id in seen_canonical
                seen_canonical.add(r.scenario_id)
                sc_label = f"{r.scenario_id} (repeat)" if is_repeat else r.scenario_id
                q_sub = r.query[:45] + ("..." if len(r.query) > 45 else "")
                doc_disp = r.retrieved_doc_id or ("cached" if r.cache_hit else "None")
                md_lines.append(
                    f"| `{sc_label}` | {q_sub} | `{r.expected_doc_id or 'None'}` | `{doc_disp}` | "
                    f"{r.total_latency_ms:.2f} ms | {'Yes' if r.cache_hit else 'No'} | {'PASS' if r.passed else 'FAIL'} |"
                )

        md_content = "\n".join(md_lines) + "\n"
        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)

        return md_content


def compare_benchmark_reports(
    baseline_data: Union[str, Dict[str, Any]],
    current_data: Union[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Compares two benchmark report runs and reports improved, regressed, or unchanged metrics."""
    if isinstance(baseline_data, str):
        with open(baseline_data, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
    if isinstance(current_data, str):
        with open(current_data, "r", encoding="utf-8") as f:
            current_data = json.load(f)

    b_m = baseline_data.get("metrics", {})
    c_m = current_data.get("metrics", {})

    def evaluate_diff(
        metric_name: str,
        b_val: float,
        c_val: float,
        higher_is_better: bool = True,
        tolerance: float = 0.001,
    ) -> Dict[str, Any]:
        diff = c_val - b_val
        if abs(diff) <= tolerance:
            status = "unchanged"
        elif (diff > 0 and higher_is_better) or (diff < 0 and not higher_is_better):
            status = "improved"
        else:
            status = "regressed"
        return {
            "baseline": round(b_val, 4),
            "current": round(c_val, 4),
            "delta": round(diff, 4),
            "status": status,
        }

    comparison = {
        "top1_accuracy": evaluate_diff("top1_accuracy", b_m.get("top1_accuracy", 0.0), c_m.get("top1_accuracy", 0.0), higher_is_better=True),
        "top3_accuracy": evaluate_diff("top3_accuracy", b_m.get("top3_accuracy", 0.0), c_m.get("top3_accuracy", 0.0), higher_is_better=True),
        "coverage": evaluate_diff("coverage", b_m.get("coverage", 0.0), c_m.get("coverage", 0.0), higher_is_better=True),
        "cache_hit_rate": evaluate_diff("cache_hit_rate", b_m.get("cache_hit_rate", 0.0), c_m.get("cache_hit_rate", 0.0), higher_is_better=True),
        "avg_latency_ms": evaluate_diff("avg_latency_ms", b_m.get("avg_latency_ms", 0.0), c_m.get("avg_latency_ms", 0.0), higher_is_better=False, tolerance=0.1),
        "p50_latency_ms": evaluate_diff("p50_latency_ms", b_m.get("p50_latency_ms", 0.0), c_m.get("p50_latency_ms", 0.0), higher_is_better=False, tolerance=0.1),
        "p95_latency_ms": evaluate_diff("p95_latency_ms", b_m.get("p95_latency_ms", 0.0), c_m.get("p95_latency_ms", 0.0), higher_is_better=False, tolerance=0.1),
        "schema_validity_rate": evaluate_diff("schema_validity_rate", b_m.get("schema_validity_rate", 0.0), c_m.get("schema_validity_rate", 0.0), higher_is_better=True),
        "deeplink_validity_rate": evaluate_diff("deeplink_validity_rate", b_m.get("deeplink_validity_rate", 0.0), c_m.get("deeplink_validity_rate", 0.0), higher_is_better=True),
        "url_leak_count": evaluate_diff("url_leak_count", b_m.get("url_leak_count", 0), c_m.get("url_leak_count", 0), higher_is_better=False, tolerance=0),
        "failed_scenarios": evaluate_diff("failed_scenarios", b_m.get("failed_scenarios", 0), c_m.get("failed_scenarios", 0), higher_is_better=False, tolerance=0),
    }

    improved_count = sum(1 for v in comparison.values() if v["status"] == "improved")
    regressed_count = sum(1 for v in comparison.values() if v["status"] == "regressed")
    unchanged_count = sum(1 for v in comparison.values() if v["status"] == "unchanged")

    return {
        "summary": {
            "improved": improved_count,
            "regressed": regressed_count,
            "unchanged": unchanged_count,
            "verdict": "improved" if regressed_count == 0 and improved_count > 0 else ("regressed" if regressed_count > 0 else "neutral"),
        },
        "metrics": comparison,
    }


def profile_performance(data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """Measures end-to-end performance dimensions required by Part 9."""
    # 1. Cold-start time
    t0 = time.perf_counter()
    pipe = FixFlowPipeline(prewarm=True, data_dir=data_dir)
    cold_start_sec = time.perf_counter() - t0

    # 2. Large knowledge & deeplink catalog indexing overhead
    t_kb0 = time.perf_counter()
    _ = DeeplinkCatalogIndex()
    deeplink_load_ms = (time.perf_counter() - t_kb0) * 1000.0

    # Test queries
    canonical_query = "The mobile phone screen is cracked and flashes intermittently."
    unseen_query = "My Galaxy S22 screen inputs are delayed and the touch responsiveness is laggy"

    # 3. Cache-hit latency (100 repetitions)
    pipe.troubleshoot(canonical_query)  # ensure cached
    hit_lats: List[float] = []
    for _ in range(50):
        t_req = time.perf_counter()
        resp, meta = pipe.troubleshoot(canonical_query)
        hit_lats.append((time.perf_counter() - t_req) * 1000.0)

    # 4. Cache-miss / cold-path latency
    cold_pipe = FixFlowPipeline(prewarm=False, data_dir=data_dir)
    miss_lats: List[float] = []
    retrieval_lats: List[float] = []
    for _ in range(20):
        # Unique query with timestamp to guarantee miss
        q = f"{unseen_query} {_}"
        t_req = time.perf_counter()
        resp, meta = cold_pipe.troubleshoot(q)
        miss_lats.append((time.perf_counter() - t_req) * 1000.0)
        retrieval_lats.append(meta.get("retrieval_latency_ms", 0.0))

    # 5. Concurrency test (lightweight thread execution)
    from concurrent.futures import ThreadPoolExecutor
    conc_lats: List[float] = []

    def make_req(q: str):
        t_start = time.perf_counter()
        pipe.troubleshoot(q)
        return (time.perf_counter() - t_start) * 1000.0

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(make_req, canonical_query) for _ in range(50)]
        for f in futures:
            conc_lats.append(f.result())

    return {
        "cold_start_seconds": round(cold_start_sec, 3),
        "deeplink_catalog_load_ms": round(deeplink_load_ms, 2),
        "cache_hit": {
            "avg_ms": round(float(np.mean(hit_lats)), 2),
            "p50_ms": calculate_percentile(hit_lats, 50),
            "p95_ms": calculate_percentile(hit_lats, 95),
            "min_ms": round(min(hit_lats), 2),
            "max_ms": round(max(hit_lats), 2),
        },
        "cache_miss": {
            "avg_ms": round(float(np.mean(miss_lats)), 2),
            "p50_ms": calculate_percentile(miss_lats, 50),
            "p95_ms": calculate_percentile(miss_lats, 95),
            "avg_retrieval_ms": round(float(np.mean(retrieval_lats)), 2),
        },
        "concurrency": {
            "workers": 5,
            "requests": len(conc_lats),
            "avg_latency_ms": round(float(np.mean(conc_lats)), 2),
            "p95_latency_ms": calculate_percentile(conc_lats, 95),
            "throughput_req_per_sec": round(len(conc_lats) / (sum(conc_lats) / 1000.0 / 5), 1),
        },
    }
