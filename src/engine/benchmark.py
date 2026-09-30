"""Measure end-to-end FixFlow pipeline behavior over a query set."""

from dataclasses import dataclass
import json
import time
from typing import Any, Dict, Iterable, List, Optional, Union

import numpy as np
from pydantic import ValidationError

from src.engine.validator import detect_url_leakage
from src.schema import ContextDeeplinkResponse


@dataclass(frozen=True)
class BenchmarkCase:
    """A query and optional identifiers for its source and variation."""

    query: str
    query_index: Optional[int] = None
    variation_index: Optional[int] = None


@dataclass
class BenchmarkReport:
    """Per-query observations and aggregate rates from a benchmark run."""

    summary: Dict[str, Union[int, float]]
    results: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {"summary": self.summary, "results": self.results}


def _response_payload(response: Any) -> Optional[Dict[str, Any]]:
    if isinstance(response, ContextDeeplinkResponse):
        return response.model_dump(mode="json")
    if isinstance(response, dict):
        return response
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        return payload if isinstance(payload, dict) else None
    return None


def _summarize(results: List[Dict[str, Any]]) -> Dict[str, Union[int, float]]:
    count = len(results)
    latencies = [float(result["latency_ms"]) for result in results]

    def rate(field: str) -> float:
        if not count:
            return 0.0
        return sum(bool(result[field]) for result in results) / count

    return {
        "sample_count": count,
        "p50_latency_ms": float(np.percentile(latencies, 50)) if latencies else 0.0,
        "p95_latency_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "cache_hit_rate": rate("cache_hit"),
        # Coverage means the pipeline returned at least one goal containing
        # at least one action. Schema and leakage are reported separately.
        "coverage_rate": rate("covered"),
        "schema_validity_rate": rate("schema_valid"),
        "url_leakage_rate": rate("url_leaked"),
        "url_leak_count": sum(int(result["url_leak_count"]) for result in results),
    }


def run_benchmark(
    pipeline: Any,
    queries: Iterable[Union[str, BenchmarkCase]],
) -> BenchmarkReport:
    """Run each query through ``pipeline.troubleshoot`` and measure the call.

    Latency is wall-clock time around the actual pipeline call. Cache-hit rate
    comes from each call's returned telemetry. Coverage requires a non-empty
    context with at least one action; schema validity checks the response
    against ``ContextDeeplinkResponse``; URL leakage is evaluated on the full
    serialized response while the validator permits internal Bixby deeplinks.
    Pipeline errors are retained as failed samples so aggregate denominators
    remain the number of attempted queries.
    """
    results: List[Dict[str, Any]] = []

    for item in queries:
        case = item if isinstance(item, BenchmarkCase) else BenchmarkCase(query=str(item))
        started = time.perf_counter()
        response = None
        telemetry: Dict[str, Any] = {}
        error = None
        try:
            response, telemetry = pipeline.troubleshoot(case.query)
        except Exception as exc:  # Record failed cases rather than hiding them.
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        payload = None
        schema_valid = False
        covered = False
        leaks: List[str] = []
        if response is not None:
            try:
                payload = _response_payload(response)
            except Exception as exc:
                error = error or f"Serialization error: {type(exc).__name__}: {exc}"

            if payload is not None:
                contexts = payload.get("contexts")
                covered = bool(
                    isinstance(contexts, list)
                    and any(
                        isinstance(context, dict)
                        and isinstance(context.get("actions"), list)
                        and context.get("actions")
                        for context in contexts
                    )
                )
                try:
                    ContextDeeplinkResponse.model_validate(payload)
                    schema_valid = True
                except (ValidationError, TypeError, ValueError):
                    schema_valid = False

                leaks = detect_url_leakage(json.dumps(payload, ensure_ascii=False))

        results.append(
            {
                "query_index": case.query_index,
                "variation_index": case.variation_index,
                "query": case.query,
                "latency_ms": elapsed_ms,
                "cache_hit": bool(telemetry.get("cache_hit", False)),
                "covered": covered,
                "schema_valid": schema_valid,
                "url_leaked": bool(leaks),
                "url_leak_count": len(leaks),
                "url_leaks": leaks,
                "error": error,
                "response": payload,
            }
        )

    return BenchmarkReport(summary=_summarize(results), results=results)


def render_markdown_report(report: BenchmarkReport) -> str:
    """Format aggregate benchmark metrics as a compact Markdown report."""
    metrics = report.summary
    count = int(metrics["sample_count"])
    percentage_fields = (
        ("Cache hit rate", "cache_hit_rate"),
        ("Coverage", "coverage_rate"),
        ("Schema validity", "schema_validity_rate"),
        ("URL leakage rate", "url_leakage_rate"),
    )
    lines = [
        "# FixFlow Benchmark Report",
        "",
        f"Samples: {count}",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| P50 latency | {float(metrics['p50_latency_ms']):.2f} ms |",
        f"| P95 latency | {float(metrics['p95_latency_ms']):.2f} ms |",
    ]
    for label, key in percentage_fields:
        lines.append(f"| {label} | {float(metrics[key]) * 100:.1f}% |")
    lines.extend(
        [
            f"| URL leak matches | {int(metrics['url_leak_count'])} |",
            "",
            "Latency is measured around each `FixFlowPipeline.troubleshoot` call. "
            "Coverage counts responses with at least one goal and one action. "
            "Schema validity checks the response model shape; URL leakage checks "
            "the serialized response and ignores allowed `bixby://` deeplinks.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "BenchmarkCase",
    "BenchmarkReport",
    "render_markdown_report",
    "run_benchmark",
]
