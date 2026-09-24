"""Deeplink Retrieval & Matching Engine for FixFlow.

Matches UI troubleshooting actions to the 578 masked Galaxy Settings deeplinks
using rich descriptive metadata (message, description, qna_description).

Rules:
- Deeplinks must be retrieved from the catalog; NEVER invent or modify URIs.
- Match on metadata, NEVER on the masked URI hash itself.
- If no catalog entry matches an auto action, fallback to bixby://dummy_positive
  with a concrete description and message.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.schema import Deeplink, ValidationDeepLink

DEFAULT_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "deeplinks.json",
)


def _clean_text(text: str) -> str:
    """Normalizes text for matching by removing special characters and lowering."""
    if not text:
        return ""
    return re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()


class DeeplinkMatcher:
    """Retrieves and matches Settings deeplinks using hybrid TF-IDF and keyword scoring."""

    def __init__(self, catalog_path: str = DEFAULT_CATALOG_PATH):
        self.catalog_path = catalog_path
        self.entries: List[Dict[str, Any]] = []
        self.documents: List[str] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        self._load_and_index()

    def _load_and_index(self) -> None:
        if not os.path.exists(self.catalog_path):
            return

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_deeplinks = data.get("deeplinks", [])
        for item in raw_deeplinks:
            uri = item.get("deeplink", "")
            if not uri or uri == "bixby://dummy_positive":
                continue

            self.entries.append(item)
            # Combine rich metadata fields for retrieval
            message = item.get("message") or ""
            desc = item.get("description") or ""
            qna = item.get("qna_description") or ""
            doc_text = f"{message} {message} {desc} {qna}"
            self.documents.append(_clean_text(doc_text))

        if self.documents:
            self.vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                stop_words="english",
                sublinear_tf=True,
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(self.documents)

    def find_best_match(
        self,
        query: str,
        threshold: float = 0.15,
    ) -> Tuple[Optional[Deeplink], Optional[ValidationDeepLink], float]:
        """Finds the most semantically relevant Settings deeplink for an action or step.
        
        Args:
            query: Action name, steps, or screen description.
            threshold: Minimum cosine similarity score required for catalog match.
            
        Returns:
            (actionableDeeplink, validationDeeplink, match_score)
        """
        cleaned_query = _clean_text(query)
        if not cleaned_query or self.vectorizer is None or self.tfidf_matrix is None:
            return self._build_dummy_fallback(query), None, 0.0

        query_vec = self.vectorizer.transform([cleaned_query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score < threshold:
            # Fallback to mandated generic placeholder
            return self._build_dummy_fallback(query), None, best_score

        matched_item = self.entries[best_idx]
        actionable_dl = Deeplink(
            deeplink=matched_item["deeplink"],
            description=matched_item.get("description", "Opens device settings screen on the device."),
            message=matched_item.get("message", "Open Settings"),
            originalType=matched_item.get("originalType", "onClickURL"),
        )

        validation_dl = None
        val_data = matched_item.get("validation")
        if isinstance(val_data, dict) and val_data.get("deeplink"):
            validation_dl = ValidationDeepLink(
                deeplink=val_data["deeplink"],
                key=val_data.get("key", matched_item.get("message", "Setting")),
                resultType=val_data.get("resultType", "boolean"),
                condition=val_data.get("condition", "equal"),
                value=str(val_data.get("value", "True")),
            )

        return actionable_dl, validation_dl, best_score

    def _build_dummy_fallback(self, context: str) -> Deeplink:
        """Constructs the mandated bixby://dummy_positive fallback with a 5-7 word description."""
        # Clean context for meaningful fallback message
        words = [w.capitalize() for w in re.findall(r"[a-zA-Z]+", context)[:4]]
        screen_name = " ".join(words) if words else "Device"
        return Deeplink(
            deeplink="bixby://dummy_positive",
            description=f"It will configure {screen_name.lower()} settings safely",
            message=f"Open {screen_name} Settings",
            originalType="placeholder",
        )
