# FixFlow Development Log

This is a handover chronology based on the project work recorded for this checkout, not a reconstruction of Git commit history. “Implemented” describes code currently present; planned work is listed separately.

## 1. Initial troubleshooting pipeline — implemented

The starting project already had a pipeline to retrieve SIIS content, extract a structured response, validate it, and serve it through FastAPI. The initial working baseline was reported as having 35 passing tests. The cache-miss path remains the main product path and has not been replaced by benchmark-specific response mappings.

## 2. Semantic cache — implemented

An in-memory semantic cache was integrated with the pipeline. L1 uses normalized exact matching. L2 uses scikit-learn TF-IDF and cosine similarity with a configurable minimum score. The cache contributes hit/miss telemetry to the API and benchmark. Canonical prewarming validates before insertion; the normal miss path currently inserts its response even after a validation failure (see known issues).

## 3. Canonical scenario prewarming — implemented

Prewarming was made scenario-aware from canonical SIIS `original_query` text. It retains model/form-factor anchors, prioritizes distinctive terms across the SIIS set, and generates local lexical equivalents. This lets common paraphrases reuse validated responses while reducing generic cross-scenario collisions. The benchmark generator does not bulk-prewarm its 180 variations.

## 4. Threshold and compatibility improvements — implemented

Manual semantic checks exposed false-positive L2 hits: unrelated symptoms could pass on broad lexical similarity. A generic compatibility guard was added after the configured score threshold. It checks device/form-factor consistency, distinctive troubleshooting symptom agreement, meaningful overlap, and display-size versus text-size distinctions. Exact L1 matching was preserved. Rejected semantic candidates become normal retrieval misses; maximizing hit rate is intentionally not the sole objective.

The threshold remains configurable with `FIXFLOW_CACHE_THRESHOLD` (default `0.30`). The deeplink matcher has a different threshold (`0.15`) and is not controlled by that variable.

## 5. Retrieval/RAG improvements — implemented, still heuristic

The retriever builds scenario-oriented searchable text and combines TF-IDF, BM25, device affinity, local synonym expansion, and symptom/context reranking. The intent was to reduce irrelevant influence from generic procedure text and increase sensitivity to scenario-defining symptoms. Device recognition and symptom extraction use regex/rule families. No external embedding service or generative model was introduced.

Known limitation: these scoring rules have not been validated with a semantic relevance benchmark, and raw SIIS scenario content itself is sometimes inconsistent. See `PROJECT_DETAILS.md` for concrete follow-up areas.

## 6. Deeplink integration and audit — implemented; semantic quality unresolved

Actionable/validation deeplink fields are defined in `src/schema.py` under `StepGroup`. `SIISExtractor` invokes `DeeplinkMatcher` for automatic actions. The matcher ranks the separate `data/deeplinks.json` catalog using TF-IDF over descriptive metadata and returns catalog URIs and optional validation metadata. If no record clears the matcher threshold, it returns the dummy Bixby placeholder.

Auditing established that the data flow is connected, but that catalog validity is not action relevance: nearest-neighbor matching can attach a valid but inappropriate Settings link. No individual query, scenario, or URI mapping should be added to fix this; improve generic action/link compatibility and evaluation.

## 7. Benchmarking — implemented

`src/engine/variations.py` contains deterministic curated paraphrases for the 20 official SIIS queries (nine each). `scripts/generate_results.py` invokes the normal `FixFlowPipeline.troubleshoot` path for all 180, without explicitly adding those variations to cache prewarm. `src/engine/benchmark.py` records actual wall-clock pipeline call latency and response/cache telemetry, then calculates P50/P95, cache hit rate, response coverage, Pydantic schema validity, and URL leakage. It writes `results.jsonl` and `benchmark_report.md`.

Current saved report snapshot: 180 samples; 85.0% cache hit rate; 100.0% coverage; 100.0% schema validity; 0.0% URL leakage; P50 0.69 ms; P95 3.98 ms. These values can vary when rerun. Importantly, this benchmark does not assess retrieved scenario correctness or deeplink semantic agreement.

The separate `benchmark_report.json` currently contains an older evaluator report with a different schema and timestamp; the variation generator does not update it.

## 8. Testing and validation — present, not rerun for these docs

The repository contains unit/integration tests for the API, benchmark, deeplink matcher, device detector, extractor, action ordering, pipeline, preprocessing, RAG, retrieval, cache, and validator. The earlier baseline of 35 passing tests was reported during initial work. This documentation-only task did not modify or run tests; do not interpret that baseline as a fresh validation of the current checkout.

Static source inspection also found that `src/engine/evaluator.py` imports `FixFlowBenchmark` and `load_canonical_scenarios`, which are absent from the current `src/engine/benchmark.py`. That separate evaluator path appears stale and was not exercised here.

## 9. Current implemented state

- FastAPI endpoints: `GET /health`, `POST /v1/troubleshoot`.
- Cache-first pipeline with L1 exact and guarded L2 semantic matching.
- Canonical SIIS prewarming and standard retrieval fallback.
- Scenario retrieval with TF-IDF, BM25, device scoring, and rule-based reranking.
- SIIS-derived structured output, automatic/manual/critical categories, and deterministic order.
- Deeplink metadata match, optional validation link, and dummy fallback.
- Pydantic/rule validation and external URL leakage detection.
- 180-query benchmark script that produces JSONL and Markdown artifacts.
- Canonical prewarm only inserts validated responses; the normal miss path currently also inserts the raw response after validation failure, a cache-safety issue still to address.

## 10. Planned, not implemented

- Labeled semantic retrieval and deeplink-quality evaluation.
- Generic action-to-deeplink entailment/compatibility scoring.
- SIIS source curation and provenance/quality review.
- Calibrated confidence or a principled abstention policy for retrieval and link matching.
- Operational persistence, feedback learning, or production monitoring beyond current in-process telemetry.
- Fixing the retrieval-weight configuration wiring discrepancy.

See `PROJECT_DETAILS.md` for known issues and a suggested next-developer plan.
