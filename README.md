# FixFlow

FixFlow is a Samsung device troubleshooting prototype. It takes a natural-language issue, finds a relevant scenario in the supplied SIIS (Samsung Internal Information Store) knowledge set, and returns a structured troubleshooting plan with catalog-backed Settings deeplinks where available.

## Problem and approach

Troubleshooting content is difficult to use when it is returned as long, inconsistent text. FixFlow turns the available SIIS material into a small, ordered plan with a goal, actions, steps, and optional deeplinks. It combines an in-memory semantic cache with hybrid retrieval and deterministic parsing and validation. The current implementation is a rules-and-retrieval system: it does not call a generative AI model or an external embedding service.

## Request to response

1. Normalize the query for cache lookup.
2. Check the exact L1 cache, then attempt an L2 TF-IDF cosine-similarity match subject to a configurable threshold and semantic-compatibility guard.
3. On a cache miss, retrieve a SIIS scenario using TF-IDF, BM25, device affinity, and symptom/context reranking.
4. Parse the selected SIIS title and text into a goal, actions, and step groups.
5. Match eligible automatic actions against metadata in the supplied deeplink catalog.
6. Order actions, validate the response shape and rule constraints, return the result, and add it to the in-memory cache.

The output is a `ContextDeeplinkResponse` with `contexts[]` goals. Each goal contains a title, score, and actions. Each action has a name, description, category (`auto`, `manual`, or `critical`), and `stepGroups[]`. A step group contains steps and optional `actionableDeeplink` and `validationDeeplink` objects.

## Components and knowledge

- **Semantic cache:** `src/engine/semantic_cache.py` keeps L1 normalized exact matches and L2 TF-IDF semantic matches in memory. Similarity alone is not enough for an L2 hit: the guard also checks threshold, device/form-factor consistency, symptom-family agreement, and meaningful token overlap. Canonical SIIS entries are prewarmed by `FixFlowPipeline`; benchmark paraphrases are sent through the pipeline normally.
- **Retrieval/RAG:** `src/engine/retriever.py` combines TF-IDF word n-gram similarity, local Okapi BM25 scoring, device affinity, and deterministic symptom/context reranking. `src/engine/knowledge_store.py` loads or builds searchable documents from the raw scenarios.
- **SIIS knowledge:** `data/siis_responses.json` contains the 20 supplied canonical troubleshooting records. `data/processed_knowledge/processed_siis.json` is a derived searchable representation and is rebuilt when the raw file is newer or the processed file is absent.
- **Deeplinks:** `data/deeplinks.json` is a separate catalog of masked Bixby URI records with descriptions, messages, types, and optional validation metadata. `src/engine/deeplink_matcher.py` ranks catalog metadata using TF-IDF cosine similarity; it does not derive URIs from their hashes. Validation links are present only for some catalog records. Automatic actions are eligible for matching; manual and critical actions generally have no deeplink. A below-threshold match uses the mandated `bixby://dummy_positive` placeholder.
- **Validation and safety:** `src/engine/validator.py` checks Pydantic schema, formatting/rule constraints, catalog URI membership, required auto-action deeplinks, and external URL leakage. URL checks allow internal `bixby://` URIs. Validation checks consistency/shape, not whether a retrieved scenario or deeplink is semantically correct.

## Example

Run the Python pipeline:

```python
from src.engine.pipeline import FixFlowPipeline

pipeline = FixFlowPipeline()
response, telemetry = pipeline.troubleshoot(
    "My Galaxy S22 touchscreen responds slowly"
)
print(response.model_dump(mode="json"))
print(telemetry)
```

The output shape is `{"contexts": [{"goal": "...", "title": "...", "score": 0.95, "actions": [{"actionName": "...", "description": "...", "category": "auto", "stepGroups": [{"steps": ["..."], "actionableDeeplink": {"deeplink": "bixby://...", "description": "...", "message": "..."}, "validationDeeplink": null}]}]}]}`. Deeplink values and response content depend on retrieval; this fragment illustrates the schema, not a guaranteed result. See [`data/sample_output.json`](data/sample_output.json) for a full example artifact.

## Run locally

Python 3.10 or newer is recommended. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the REST API:

```bash
uvicorn src.api:app --reload
```

The API exposes `GET /health` and `POST /v1/troubleshoot`. Example request:

```bash
curl -X POST http://127.0.0.1:8000/v1/troubleshoot \
  -H 'Content-Type: application/json' \
  -d '{"query":"My Galaxy tablet screen goes black when opening mail"}'
```

Run the pipeline directly with the Python example above. To generate the current 180-case variation benchmark and overwrite the root `results.jsonl` and `benchmark_report.md` artifacts:

```bash
python scripts/generate_results.py --output-dir .
```

Each JSONL line contains a query, measured pipeline latency, cache telemetry, coverage/schema/leakage observations, error if any, and serialized response. The Markdown report summarizes aggregate metrics. The script writes these two artifacts; it does not refresh the separate legacy `benchmark_report.json` file.

## Benchmark snapshot

The checked-in `benchmark_report.md` currently reports 180 samples, 85.0% cache hit rate, 100.0% coverage, 100.0% schema validity, 0.0% URL leakage, P50 0.69 ms, and P95 3.98 ms. These are one local run's measurements, not latency guarantees. The benchmark measures execution and structural gates; it does not score retrieval relevance or deeplink/action semantic agreement.

## Configuration

Runtime options are read in `src/config.py`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `FIXFLOW_DATA_DIR` | `data/` | Source and processed knowledge directory |
| `FIXFLOW_CACHE_THRESHOLD` | `0.30` | Minimum L2 cache similarity before compatibility checks |
| `FIXFLOW_CACHE_PREWARM` | `true` | Prewarm canonical SIIS cache entries |
| `FIXFLOW_TOP_K` | `3` | Retrieval candidate count |
| `FIXFLOW_MAX_QUERY_LENGTH` | `2000` | API query length limit |
| `FIXFLOW_LOG_LEVEL` | `INFO` | Log level setting |

Retrieval weight constants also exist in configuration, but the current pipeline does not pass those configured weights into `SIISRetriever`; see [known limitations](docs/PROJECT_DETAILS.md#known-issues--follow-up-work).

## Project layout

```text
src/api.py                    FastAPI endpoints
src/config.py                 Paths and environment-based defaults
src/schema.py                 Pydantic response and deeplink schema
src/engine/                   Cache, retrieval, extraction, deeplink, validation, benchmark
data/                         SIIS source, deeplink catalog, sample and derived data
scripts/generate_results.py   Variation benchmark runner and artifact writer
tests/                        Unit and integration tests
docs/                         Architecture, project handover, development log
results.jsonl                 Per-query benchmark output
benchmark_report.md           Aggregate benchmark snapshot
```

## Technologies

Python, FastAPI, Pydantic, scikit-learn TF-IDF/cosine similarity, NumPy, a local BM25 implementation with optional `rank-bm25` acceleration, and pytest. Dependencies are listed in `requirements.txt`.

## Limitations and next steps

The knowledge set is small and source scenario titles/content are not always aligned. TF-IDF/BM25 retrieval and the hand-built reranker can select the wrong scenario for ambiguous phrasing. Deeplink matching is a separate shallow TF-IDF nearest-neighbor step and can attach a catalog-valid but semantically mismatched action link. The validator and present benchmark do not detect these semantic failures. The normal cache-miss path also stores the returned response even when validation reports it invalid. There is no online learning, persistent response cache, generative model, or external vector database; the older evaluator module also appears out of sync with the current benchmark API.

Recommended follow-up is a labeled retrieval/deeplink relevance evaluation, cleanup and curation of SIIS source records, stronger action-to-link compatibility scoring, and tests for semantic false positives and source/action consistency. See [`docs/PROJECT_DETAILS.md`](docs/PROJECT_DETAILS.md) for implementation detail and handover notes.

## Documentation

- [Detailed project handover](docs/PROJECT_DETAILS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)


## Demo Video
[Watch the FixFlow Demo Video](https://drive.google.com/file/d/11pl5hDF-wlilE2IsK0x64KEpG8sxf1s4/view?usp=drivesdk)
