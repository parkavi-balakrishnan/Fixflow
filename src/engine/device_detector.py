"""Device & Model Intelligence Detector for FixFlow RAG.

Extracts device families, form factors, and specific Samsung Galaxy model names
from natural language queries and explicit request parameters to enable
device-aware troubleshooting retrieval.
"""
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set

from src.engine.preprocessor import KnowledgeDocument

# Detection patterns for Samsung device families
_FAMILY_PATTERNS = {
    "foldable": re.compile(
        r"\b(galaxy\s*z\s*flip\s*\d*|galaxy\s*flip\s*\d*|z\s*flip\s*\d*|galaxy\s*z\s*fold\s*\d*|galaxy\s*fold\s*\d*|z\s*fold\s*\d*|z\s*trifold|foldable|inner\s*screen|cover\s*screen|where\s*it\s*folds)\b",
        re.IGNORECASE,
    ),
    "tablet": re.compile(
        r"\b(galaxy\s*tab(?:\s*[a-z0-9]+)?|tablet|a115g\s*tablet|tab\s*s\d*|tab\s*a\d*)\b",
        re.IGNORECASE,
    ),
    "wearable": re.compile(
        r"\b(galaxy\s*watch\s*\d*|smart\s*watch|galaxy\s*buds|wearable)\b",
        re.IGNORECASE,
    ),
    "tv": re.compile(
        r"\b(samsung\s*tv|smart\s*tv|qled|oled|lifestyle\s*tv|projector|screen\s*mirroring\s*to\s*(?:your\s*)?tv|cast(?:ing)?\s*to\s*(?:a\s*)?tv)\b",
        re.IGNORECASE,
    ),
    "pc": re.compile(
        r"\b(galaxy\s*book|windows\s*pc|personal\s*computer|laptop|notebook|netbook)\b",
        re.IGNORECASE,
    ),
    "smartphone": re.compile(
        r"\b(galaxy\s*s\d{1,2}|s\*{3,5}\s*ultra|galaxy\s*a\d{2,3}|galaxy\s*phone|smartphone|mobile\s*phone|phone|handset)\b",
        re.IGNORECASE,
    ),
}

# Specific model patterns
_MODEL_PATTERNS = [
    re.compile(r"\b(galaxy\s*s26\s*ultra|s26\s*ultra)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*s25|s25)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*s24\s*ultra|s24\s*ultra|galaxy\s*s24|s24)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*s22|s22)\b", re.IGNORECASE),
    re.compile(r"\b(s\*{3,5}\s*ultra)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*z\s*flip\s*7|z\s*flip\s*7|flip\s*7)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*z\s*flip\s*6|z\s*flip\s*6|flip\s*6)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*z\s*fold\s*\d*|z\s*fold\s*\d*|z\s*trifold)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*a17|a17)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*a15|galaxy\s*a16|a15/a16|a15|a16)\b", re.IGNORECASE),
    re.compile(r"\b(samsung\s*a115g|a115g)\b", re.IGNORECASE),
    re.compile(r"\b(galaxy\s*watch\s*\d*)\b", re.IGNORECASE),
]


@dataclass
class DeviceContext:
    """Represents detected device metadata from a query or explicit inputs."""
    raw_query: str
    families: Set[str] = field(default_factory=set)
    models: List[str] = field(default_factory=list)
    is_explicit: bool = False

    def is_empty(self) -> bool:
        return len(self.families) == 0 and len(self.models) == 0


class DeviceDetector:
    """Detects Samsung device family and model to evaluate device affinity."""

    def detect(self, query: str, explicit_device: Optional[str] = None) -> DeviceContext:
        """Extracts device context from natural query or explicit device parameter."""
        combined_text = f"{explicit_device or ''} {query}".strip()
        families: Set[str] = set()
        models: List[str] = []

        for family_name, pattern in _FAMILY_PATTERNS.items():
            if pattern.search(combined_text):
                families.add(family_name)

        for model_pattern in _MODEL_PATTERNS:
            match = model_pattern.search(combined_text)
            if match:
                clean_model = " ".join(match.group(0).lower().split())
                if clean_model not in models:
                    models.append(clean_model)

        # Default to smartphone if general phone terms found
        if not families and any(w in combined_text.lower() for w in ["phone", "screen", "display"]):
            families.add("smartphone")

        return DeviceContext(
            raw_query=query,
            families=families,
            models=models,
            is_explicit=bool(explicit_device),
        )

    def calculate_affinity(self, context: DeviceContext, doc: KnowledgeDocument) -> float:
        """Calculates device compatibility score between 0.0 and 1.0.
        
        1.0: Full match / compatible device family or model
        0.7: Partial or generic mobile compatibility
        0.3: Peripheral or secondary compatibility
        0.1: Cross-category mismatch (e.g. TV-only query on phone-only doc)
        """
        if context.is_empty():
            return 0.7  # Neutral default when no device specified

        doc_cats_lower = {c.lower() for c in doc.device_categories}
        doc_models_lower = {m.lower() for m in doc.device_models}

        # 1. Exact model match in document
        for m in context.models:
            for dm in doc_models_lower:
                if m in dm or dm in m:
                    return 1.0

        # 2. TV / Casting scenario
        if "tv" in context.families:
            if any("tv" in c or "qled" in c or "oled" in c for c in doc_cats_lower):
                return 1.0
            return 0.2

        # 3. Tablet scenario
        if "tablet" in context.families:
            if "tablet" in doc_cats_lower or any("tab" in m for m in doc_models_lower):
                return 1.0
            return 0.4

        # 4. Foldable scenario
        if "foldable" in context.families:
            if any("fold" in m or "flip" in m for m in doc_models_lower) or "smartphone" in doc_cats_lower:
                return 1.0
            return 0.5

        # 5. Wearable scenario
        if "wearable" in context.families:
            if "wearable" in doc_cats_lower or any("watch" in m for m in doc_models_lower):
                return 1.0
            return 0.2

        # 6. Smartphone scenario
        if "smartphone" in context.families:
            if "smartphone" in doc_cats_lower or "others mobile" in doc_cats_lower:
                return 1.0

        return 0.6
