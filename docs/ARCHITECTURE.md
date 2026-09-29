# FixFlow Architecture

## Request flow

```text
Caller (Python API or REST)
          |
          v
   FixFlowPipeline.troubleshoot(query, ...)
          |
          v
   Query normalization
          |
          +------------------------------+
          |                              |
          v                              |
   SemanticCache.get                    |
      |                                 |
      +-- L1 normalized exact lookup    |
      +-- L2 TF-IDF cosine +            |
          threshold + compatibility guard
          | hit                          | miss
          v                              v
   Cached structured response     SIISRetriever
                                     |
                         TF-IDF + BM25 + device affinity
                         + symptom/context reranking
                                     |
                                     v
                               SIIS scenario
                                     |
                                     v
                                SIISExtractor
                         title/content -> goal/actions/
                         steps/action categories
                                     |
                    eligible auto action only
                                     v
                              DeeplinkMatcher
                    catalog metadata TF-IDF match;
                    optional validation link or fallback
                                     |
                                     v
                            Deterministic ordering
                                     |
                                     v
                           ResponseValidator
                                     |
                                     +--> response added to cache
                                     |
                                     v
                         ContextDeeplinkResponse + telemetry
```

The HTTP adapter in `src/api.py` calls the pipeline, returns a `ContextDeeplinkResponse`, and exposes cache/source/latency/retrieval/validation/leakage observations in response headers. The validator does not repair or semantically rerank an invalid result.

On the normal miss path, `FixFlowPipeline.troubleshoot` currently caches the response even when validation fails and the raw extracted response is returned. Canonical prewarming, by contrast, inserts only responses that pass validation.

## Runtime modules

- `src/engine/pipeline.py`: orchestration, canonical SIIS loading, prewarming, cache-first lookup, retrieval fallback, extraction, validation, cache population, and telemetry.
- `src/engine/semantic_cache.py`: in-memory L1 exact and L2 TF-IDF semantic cache, with compatibility filtering.
- `src/engine/knowledge_store.py` and `src/engine/preprocessor.py`: parse raw SIIS into structured searchable documents; processed data is persisted under `data/processed_knowledge/`.
- `src/engine/retriever.py`, `src/engine/bm25.py`, and `src/engine/device_detector.py`: lexical/semantic retrieval, device affinity, and deterministic symptom reranking.
- `src/engine/extractor.py`: parse SIIS text into schema objects and classify/order actions.
- `src/engine/deeplink_matcher.py`: select a deeplink by similarity against separate catalog descriptions/messages.
- `src/engine/ordering.py`: stable auto/manual/critical action ordering and disruptive-action promotion.
- `src/engine/validator.py` and `src/schema.py`: response shape, formatting, URI membership, and URL-leak validation.
- `src/engine/benchmark.py`, `src/engine/variations.py`, `scripts/generate_results.py`: variation generation, actual pipeline measurement, and JSONL/Markdown output.
