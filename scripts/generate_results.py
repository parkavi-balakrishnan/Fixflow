#!/usr/bin/env python3
"""Run the Samsung query variation benchmark and write its artifacts."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engine.benchmark import (  # noqa: E402
    BenchmarkCase,
    render_markdown_report,
    run_benchmark,
)
from src.engine.pipeline import FixFlowPipeline  # noqa: E402
from src.engine.variations import QueryVariationGenerator  # noqa: E402


def load_benchmark_cases(data_path: Path) -> List[BenchmarkCase]:
    """Load the 20 official queries and create one case per curated variation."""
    catalog: Dict[str, Any] = json.loads(data_path.read_text(encoding="utf-8"))
    official_queries = catalog.get("responses", [])
    if len(official_queries) != 20:
        raise ValueError(
            f"Expected 20 official SIIS queries in {data_path}, "
            f"found {len(official_queries)}."
        )

    generator = QueryVariationGenerator()
    cases: List[BenchmarkCase] = []
    for query_index, item in enumerate(official_queries, start=1):
        query = item.get("original_query", "")
        if not query:
            raise ValueError(f"Official query {query_index} is empty.")
        variations = generator.generate_variations(query, query_index=query_index)
        if not 8 <= len(variations) <= 10:
            raise ValueError(
                f"Official query {query_index} generated {len(variations)} variations."
            )
        cases.extend(
            BenchmarkCase(
                query=variation,
                query_index=query_index,
                variation_index=variation_index,
            )
            for variation_index, variation in enumerate(variations, start=1)
        )
    return cases


def generate_results(output_dir: Path = PROJECT_ROOT) -> tuple[Path, Path]:
    """Execute all variation cases and write JSONL results plus Markdown metrics."""
    cases = load_benchmark_cases(PROJECT_ROOT / "data" / "siis_responses.json")
    # FixFlowPipeline prewarms its existing canonical entries. Variations are
    # sent through troubleshoot normally and are never explicitly prewarmed.
    report = run_benchmark(FixFlowPipeline(), cases)

    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "results.jsonl"
    markdown_path = output_dir / "benchmark_report.md"
    with jsonl_path.open("w", encoding="utf-8") as results_file:
        for result in report.results:
            results_file.write(json.dumps(result, ensure_ascii=False) + "\n")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return jsonl_path, markdown_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT,
        help="Directory for results.jsonl and benchmark_report.md (default: project root).",
    )
    args = parser.parse_args()

    results_path, report_path = generate_results(args.output_dir)
    print(f"Wrote {results_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
