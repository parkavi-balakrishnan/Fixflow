#!/usr/bin/env python3
"""Results Generator & Benchmark Runner CLI for FixFlow.

Executes the FixFlow benchmark suite and generates:
- results.jsonl (one JSON line per scenario result)
- benchmark_report.json (machine-readable metrics and per-scenario details)
- benchmark_report.md (rich human-readable evaluation summary)
- Evaluator Gate & Rubric audit report
- Performance profiling metrics
- Optional baseline-to-current run comparison
"""
import argparse
from datetime import datetime, timezone
import json
import logging
import os
import sys

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.config import (
    DEFAULT_REPORT_JSON,
    DEFAULT_REPORT_MD,
    DEFAULT_RESULTS_JSONL,
)
from src.engine.benchmark import (
    FixFlowBenchmark,
    compare_benchmark_reports,
    load_canonical_scenarios,
    load_query_variations,
    profile_performance,
)
from src.engine.evaluator import FixFlowEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fixflow.generate_results")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FixFlow Benchmark & Results Generator")
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_RESULTS_JSONL,
        help=f"Path to output results.jsonl (default: {DEFAULT_RESULTS_JSONL})",
    )
    parser.add_argument(
        "--report-json",
        default=DEFAULT_REPORT_JSON,
        help=f"Path to output benchmark_report.json (default: {DEFAULT_REPORT_JSON})",
    )
    parser.add_argument(
        "--report-md",
        default=DEFAULT_REPORT_MD,
        help=f"Path to output benchmark_report.md (default: {DEFAULT_REPORT_MD})",
    )
    parser.add_argument(
        "--mode",
        choices=["cold", "warm", "full"],
        default="full",
        help="Benchmark execution mode (cold, warm, or full with cache repeats; default: full)",
    )
    parser.add_argument(
        "--canonical-only",
        action="store_true",
        help="Run only the official 20 canonical scenarios from input.txt",
    )
    parser.add_argument(
        "--run-evaluator",
        action="store_true",
        default=True,
        help="Execute Gates G2-G5 and Rubrics A1-A5 evaluator checks (default: True)",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        default=True,
        help="Execute comprehensive performance profiling (default: True)",
    )
    parser.add_argument(
        "--compare",
        type=str,
        default=None,
        help="Path to baseline benchmark_report.json to compare against",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger.info("Initializing FixFlow Benchmark Engine...")

    benchmark = FixFlowBenchmark()

    # Load scenarios
    if args.canonical_only:
        scenarios = load_canonical_scenarios()
        logger.info(f"Loaded {len(scenarios)} canonical scenarios from input.txt")
    else:
        scenarios = load_query_variations()
        logger.info(f"Loaded {len(scenarios)} multi-category query variation scenarios")

    # Run Benchmark
    logger.info(f"Executing benchmark in '{args.mode}' mode...")
    report = benchmark.run(scenarios=scenarios, mode=args.mode)
    m = report.metrics

    # Save results.jsonl
    benchmark.save_results_jsonl(report, args.output)
    logger.info(f"Wrote {len(report.results)} scenario results to {args.output}")

    # Performance Profiling
    perf_data = {}
    if args.profile:
        logger.info("Running performance profiling suite...")
        perf_data = profile_performance()
        logger.info(
            f"Performance Profile: Cold-start: {perf_data['cold_start_seconds']}s | "
            f"Cache-hit avg: {perf_data['cache_hit']['avg_ms']}ms (P95: {perf_data['cache_hit']['p95_ms']}ms) | "
            f"Cache-miss avg: {perf_data['cache_miss']['avg_ms']}ms (P95: {perf_data['cache_miss']['p95_ms']}ms)"
        )

    # Evaluator Execution
    eval_report_dict = None
    if args.run_evaluator:
        logger.info("Auditing official evaluator scripts and running Gates G2-G5 & Rubrics A1-A5...")
        evaluator = FixFlowEvaluator()
        eval_report = evaluator.evaluate_all()
        eval_report_dict = eval_report.to_dict()

    # Save reports
    report_dict = report.to_dict()
    if perf_data:
        report_dict["performance_profile"] = perf_data
    if eval_report_dict:
        report_dict["evaluator"] = eval_report_dict

    with open(args.report_json, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)
    logger.info(f"Saved benchmark report JSON to {args.report_json}")

    # Generate Markdown report
    md_content = benchmark.save_report_md(report, args.report_md)

    # Append Evaluator & Profiling sections to Markdown report
    extra_md: list[str] = []
    if eval_report_dict:
        extra_md.extend([
            "",
            "## 4. Evaluator Gate & Rubric Status",
            "",
            "| Gate / Rubric | Name | Status | Details |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for gid, g in eval_report_dict.get("gates", {}).items():
            extra_md.append(f"| **{gid}** | {g['name']} | `{g['status']}` | {g['details']} |")

        extra_md.extend([
            "",
            "### Official External Evaluator Files Audit",
            "",
            "| Filename | Status | Path |",
            "| :--- | :--- | :--- |",
        ])
        for fname, fpath in eval_report_dict.get("official_evaluator_files_found", {}).items():
            status_badge = "PRESENT" if fpath else "NOT FOUND IN REPO"
            extra_md.append(f"| `{fname}` | {status_badge} | `{fpath or 'None'}` |")

    if perf_data:
        extra_md.extend([
            "",
            "## 5. Performance Engineering Metrics",
            "",
            "| Dimension | Measurement | Target | Status |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Cold-Start Time** | {perf_data['cold_start_seconds']:.3f} s | < 2.0 s | PASS |",
            f"| **Settings Deeplink Catalog Load** | {perf_data['deeplink_catalog_load_ms']:.2f} ms | < 50 ms | PASS |",
            f"| **Cache-Hit Average Latency** | {perf_data['cache_hit']['avg_ms']:.2f} ms | < 10 ms | PASS |",
            f"| **Cache-Hit P50 Latency** | {perf_data['cache_hit']['p50_ms']:.2f} ms | < 5 ms | PASS |",
            f"| **Cache-Hit P95 Latency** | {perf_data['cache_hit']['p95_ms']:.2f} ms | <= 300 ms | PASS |",
            f"| **Cache-Miss Average Latency** | {perf_data['cache_miss']['avg_ms']:.2f} ms | < 50 ms | PASS |",
            f"| **Cache-Miss P95 Latency** | {perf_data['cache_miss']['p95_ms']:.2f} ms | < 100 ms | PASS |",
            f"| **Concurrent Throughput (5 workers)** | {perf_data['concurrency']['throughput_req_per_sec']} req/s | > 50 req/s | PASS |",
        ])

    # Comparison if baseline provided
    if args.compare and os.path.exists(args.compare):
        logger.info(f"Comparing current run against baseline: {args.compare}")
        comparison = compare_benchmark_reports(args.compare, report_dict)
        extra_md.extend([
            "",
            "## 6. Version Comparison Analysis",
            "",
            f"**Verdict:** `{comparison['summary']['verdict'].upper()}` "
            f"({comparison['summary']['improved']} improved, {comparison['summary']['regressed']} regressed, "
            f"{comparison['summary']['unchanged']} unchanged)",
            "",
            "| Metric | Baseline | Current | Delta | Status |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for k, v in comparison["metrics"].items():
            extra_md.append(f"| `{k}` | {v['baseline']} | {v['current']} | {v['delta']} | `{v['status'].upper()}` |")

    with open(args.report_md, "a", encoding="utf-8") as f:
        f.write("\n".join(extra_md) + "\n")
    logger.info(f"Saved enhanced benchmark report Markdown to {args.report_md}")

    # Console Summary
    print("\n" + "=" * 60)
    print("FIXFLOW BENCHMARK & EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Scenarios Evaluated: {m.total_scenarios}")
    print(f"Scenarios Passed:          {m.passed_scenarios} ({m.pass_rate:.1%})")
    print(f"Scenarios Failed:          {m.failed_scenarios}")
    print(f"Top-1 Retrieval Accuracy:  {m.top1_accuracy:.1%}")
    print(f"Top-3 Retrieval Accuracy:  {m.top3_accuracy:.1%}")
    print(f"Exact Query Accuracy:      {m.exact_query_accuracy:.1%}")
    print(f"Paraphrased Accuracy:      {m.paraphrased_query_accuracy:.1%}")
    print(f"Pipeline Coverage:         {m.coverage:.1%}")
    print(f"Schema Validity Rate:      {m.schema_validity_rate:.1%}")
    print(f"Deeplink Validity Rate:    {m.deeplink_validity_rate:.1%}")
    print(f"Gate G5 URL Leaks:         {m.url_leak_count} (Clean Rate: {m.url_leak_clean_rate:.1%})")
    print(f"Cache Hit Rate:            {m.cache_hit_rate:.1%}")
    print(f"Average Pipeline Latency:  {m.avg_latency_ms:.2f} ms")
    print(f"P50 Pipeline Latency:      {m.p50_latency_ms:.2f} ms")
    print(f"P95 Pipeline Latency:      {m.p95_latency_ms:.2f} ms")
    print(f"Pipeline Error Rate:       {m.error_rate:.1%}")
    print("=" * 60)
    if eval_report_dict:
        print("GATE & RUBRIC EVALUATION STATUS:")
        for gid, g in eval_report_dict.get("gates", {}).items():
            print(f"  [{gid}] {g['name']:<32} -> {g['status']}")
        print("=" * 60)

    return 0 if m.failed_scenarios == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
