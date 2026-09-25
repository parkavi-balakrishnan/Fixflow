"""Semantic Fast-Path Cache Engine for FixFlow.

Provides two-tier caching:
- L1: Instant O(1) normalized string matching (< 1ms)
- L2: Semantic vector similarity matching for paraphrases (<= 5ms, P95 well below 300ms)

Targets:
- Cache hit P95 <= 300 ms
- Paraphrase cache hit rate >= 80%
"""
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.schema import ContextDeeplinkResponse


def normalize_query(query: str) -> str:
    """Normalizes query text for consistent hash matching."""
    if not query:
        return ""
    # Lowercase, strip punctuation and extra spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", query).lower()
    return " ".join(cleaned.split())


class SemanticCache:
    """Dual-tier fast-path semantic cache for troubleshooting responses."""

    def __init__(self, similarity_threshold: float = 0.50):
        self.similarity_threshold = similarity_threshold
        # L1: normalized_query -> ContextDeeplinkResponse
        self._exact_cache: Dict[str, ContextDeeplinkResponse] = {}
        # L2: list of raw queries and responses
        self._cached_queries: List[str] = []
        self._cached_responses: List[ContextDeeplinkResponse] = []
        # Dynamic vectorizer for L2
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix: Optional[np.ndarray] = None
        self._rebuild_needed: bool = False

        # Metrics tracking
        self.total_requests = 0
        self.l1_hits = 0
        self.l2_hits = 0
        self.misses = 0
        self.latencies_ms: List[float] = []

    def get(self, query: str) -> Tuple[Optional[ContextDeeplinkResponse], bool, float]:
        """Looks up a query in the cache.
        
        Returns:
            (cached_response_or_None, is_hit, latency_ms)
        """
        start_time = time.perf_counter()
        self.total_requests += 1

        norm = normalize_query(query)
        if not norm:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            self.misses += 1
            self.latencies_ms.append(elapsed)
            return None, False, elapsed

        # 1. Tier 1: Exact Normalized Match (L1)
        if norm in self._exact_cache:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            self.l1_hits += 1
            self.latencies_ms.append(elapsed)
            return self._exact_cache[norm], True, elapsed

        # 2. Tier 2: Semantic Vector Match (L2)
        if self._rebuild_needed and self._cached_queries:
            self._rebuild_index()

        if self._vectorizer is not None and self._tfidf_matrix is not None and len(self._cached_queries) > 0:
            query_vec = self._vectorizer.transform([norm])
            sims = cosine_similarity(query_vec, self._tfidf_matrix)[0]
            best_idx = int(np.argmax(sims))
            best_score = float(sims[best_idx])

            if best_score >= self.similarity_threshold:
                matched_response = self._cached_responses[best_idx]
                # Populate L1 for subsequent identical queries
                self._exact_cache[norm] = matched_response
                elapsed = (time.perf_counter() - start_time) * 1000.0
                self.l2_hits += 1
                self.latencies_ms.append(elapsed)
                return matched_response, True, elapsed

        # Miss
        elapsed = (time.perf_counter() - start_time) * 1000.0
        self.misses += 1
        self.latencies_ms.append(elapsed)
        return None, False, elapsed

    def put(self, query: str, response: ContextDeeplinkResponse, variations: Optional[List[str]] = None) -> None:
        """Stores a query and its response in the cache, along with any known variations."""
        norm = normalize_query(query)
        if not norm:
            return

        self._exact_cache[norm] = response
        self._cached_queries.append(norm)
        self._cached_responses.append(response)

        if variations:
            for v in variations:
                v_norm = normalize_query(v)
                if v_norm:
                    self._exact_cache[v_norm] = response
                    self._cached_queries.append(v_norm)
                    self._cached_responses.append(response)

        self._rebuild_needed = True

    def _rebuild_index(self) -> None:
        """Rebuilds the TF-IDF semantic vector index."""
        if not self._cached_queries:
            return
        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 1),
            stop_words="english",
            sublinear_tf=True,
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(self._cached_queries)
        self._rebuild_needed = False

    def p95_latency_ms(self) -> float:
        """Calculates P95 latency in milliseconds."""
        if not self.latencies_ms:
            return 0.0
        return float(np.percentile(self.latencies_ms, 95))

    def hit_rate(self) -> float:
        """Calculates current overall hit rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return (self.l1_hits + self.l2_hits) / self.total_requests
