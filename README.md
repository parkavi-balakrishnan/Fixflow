# FixFlow 🔧

### Smart Guided Troubleshooting — Samsung PRISM Generative AI Hackathon

FixFlow is a smart troubleshooting system designed to transform vague customer complaints into structured, actionable troubleshooting guidance.

Instead of requiring users to describe their problem using technical terminology, FixFlow enriches the query, retrieves relevant troubleshooting knowledge, identifies the device context, and generates an ordered set of troubleshooting actions with validated Samsung Settings deeplinks.

---

## 🚀 Key Features

- 🧠 **Query Understanding**
  - Handles vague and natural-language customer complaints.
  - Normalizes user queries before retrieval.

- 🔎 **Hybrid Knowledge Retrieval**
  - Semantic/vector retrieval
  - BM25 keyword retrieval
  - Hybrid ranking and reranking
  - Device/model-aware retrieval

- 📱 **Device-Aware Troubleshooting**
  - Detects device/form-factor information from the query.
  - Uses device context during retrieval.

- 🛠️ **Guided Troubleshooting**
  - Converts retrieved SIIS knowledge into structured troubleshooting actions.
  - Orders actions deterministically.

- 🔗 **Samsung Settings Deeplinks**
  - Matches troubleshooting actions with available Settings deeplinks.
  - Validates generated links before returning them.

- ⚡ **Semantic Cache**
  - Reuses responses for repeated/similar queries.
  - Reduces processing time for repeated requests.

- 🛡️ **Response Validation**
  - Schema validation
  - Deeplink validation
  - URL leakage detection
  - Retrieval grounding checks

- 📊 **Benchmark & Evaluation**
  - Runs the official 20-scenario dataset.
  - Tests query variations and repeated requests.
  - Measures retrieval quality, latency, cache performance, and response validity.

---

## 🏗️ Architecture

```text
User Query
    │
    ▼
┌─────────────────────┐
│ Query Preprocessing  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Semantic Cache       │
└──────────┬──────────┘
           │ Cache Miss
           ▼
┌─────────────────────┐
│ Device Detection     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│ Hybrid Retrieval                │
│                                 │
│ Semantic Retrieval + BM25       │
│          ↓                      │
│ Device/Model Affinity           │
│          ↓                      │
│ Reranking                       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────┐
│ SIIS Response        │
│ Extraction           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Deeplink Matching    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Action Ordering      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Validation & Safety  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Structured JSON      │
│ Troubleshooting      │
│ Response             │
└─────────────────────┘
