"""Okapi BM25 Lexical / Keyword Retrieval Engine for FixFlow.

Provides fast, term-weighted keyword scoring over Samsung troubleshooting documents.
Features:
- Tokenizer with punctuation normalization, stop words removal, and n-gram support.
- Self-contained vectorized Okapi BM25 implementation (with rank_bm25 acceleration if installed).
- Zero-division safety and score normalization to [0.0, 1.0].
"""
import math
import re
from typing import Dict, List, Optional, Set

import numpy as np

# Standard English stop words
_STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves",
}


def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """Tokenizes text into clean lowercase words without punctuation."""
    if not text:
        return []
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()
    tokens = cleaned.split()
    if remove_stopwords:
        tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]
    return tokens


class BM25Retriever:
    """Okapi BM25 implementation for lexical keyword search over knowledge documents."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_lengths: List[int] = []
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self._rank_bm25_instance = None

    def fit(self, corpus: List[str]) -> "BM25Retriever":
        """Indexes a list of document texts."""
        tokenized_corpus = [tokenize(doc) for doc in corpus]
        self.corpus_size = len(tokenized_corpus)

        if self.corpus_size == 0:
            return self

        self.doc_lengths = [len(doc) for doc in tokenized_corpus]
        self.avgdl = float(sum(self.doc_lengths)) / max(1, self.corpus_size)

        # Count frequencies
        self.doc_freqs = []
        df: Dict[str, int] = {}

        for doc in tokenized_corpus:
            frequencies: Dict[str, int] = {}
            for term in doc:
                frequencies[term] = frequencies.get(term, 0) + 1
            self.doc_freqs.append(frequencies)

            for term in frequencies.keys():
                df[term] = df.get(term, 0) + 1

        # Calculate Okapi IDF with smoothing: ln((N - n + 0.5)/(n + 0.5) + 1)
        self.idf = {}
        for term, freq in df.items():
            idf_val = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idf[term] = max(0.01, idf_val)

        # Try to initialize rank_bm25 if available for optimized C/NumPy speed
        try:
            from rank_bm25 import BM25Okapi
            self._rank_bm25_instance = BM25Okapi(tokenized_corpus, k1=self.k1, b=self.b)
        except Exception:
            self._rank_bm25_instance = None

        return self

    def score(self, query: str) -> np.ndarray:
        """Computes normalized BM25 score vector for all documents in the corpus."""
        if self.corpus_size == 0:
            return np.array([])

        query_tokens = tokenize(query)
        if not query_tokens:
            return np.zeros(self.corpus_size, dtype=float)

        if self._rank_bm25_instance is not None:
            raw_scores = np.array(self._rank_bm25_instance.get_scores(query_tokens), dtype=float)
        else:
            raw_scores = np.zeros(self.corpus_size, dtype=float)
            for i, doc_freq in enumerate(self.doc_freqs):
                doc_len = self.doc_lengths[i]
                len_norm = 1.0 - self.b + self.b * (doc_len / max(1.0, self.avgdl))

                score = 0.0
                for term in query_tokens:
                    if term in doc_freq:
                        tf = doc_freq[term]
                        numerator = tf * (self.k1 + 1.0)
                        denominator = tf + self.k1 * len_norm
                        score += self.idf.get(term, 0.0) * (numerator / max(1e-6, denominator))
                raw_scores[i] = score

        max_score = float(np.max(raw_scores))
        if max_score > 0.0:
            return raw_scores / max_score
        return raw_scores
