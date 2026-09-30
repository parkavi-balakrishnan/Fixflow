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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.engine.device_detector import DeviceDetector
from src.schema import ContextDeeplinkResponse


def normalize_query(query: str) -> str:
    """Normalizes query text for consistent hash matching."""
    if not query:
        return ""
    # Lowercase, strip punctuation and extra spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", query).lower()
    return " ".join(cleaned.split())


# Cache compatibility uses a compact, independent symptom vocabulary. These
# are broad intent families, not benchmark phrases or scenario identifiers.
_CACHE_SYMPTOM_TERMS = {
    "damage": {"crack", "cracked", "broken", "shattered", "bleeding", "fracture", "fractured"},
    "black_screen": {"blank", "black", "dark", "unlit", "illumination", "illuminated"},
    "touch_input": {"touch", "touchscreen", "digitizer", "input", "unresponsive"},
    "response_delay": {"slow", "slowly", "sluggish", "lag", "lagging", "laggy", "latency", "delay", "delayed", "responsiveness"},
    "display_flicker": {"flicker", "flickers", "flickering", "flash", "flashes", "flashing", "blink", "blinking", "pulse", "pulsing", "strobe", "strobes", "strobing"},
    "display_size": {"tiny", "small", "portion", "reduced", "shrink", "shrunken", "minimized", "scale", "scaling", "zoom", "size"},
    "text_size": {"text", "font", "typeface", "typography", "letters", "characters"},
    "rotation": {"rotate", "rotates", "rotated", "rotating", "rotation", "orientation", "distorted", "sideways"},
    "email": {"email", "emails", "gmail", "mail", "inbox"},
    "transfer": {"transfer", "backup", "data"},
    "multitasking": {"multiwindow", "floating", "edge", "popup"},
    "mirroring": {"mirror", "mirroring", "cast", "casting", "smartview"},
}
_PRIMARY_CACHE_SYMPTOMS = {
    "damage", "black_screen", "touch_input", "response_delay",
    "display_flicker", "display_size", "display_distortion", "rotation",
}
_DISTINCTIVE_CACHE_SYMPTOMS = {
    "email", "transfer", "multitasking", "mirroring", "text_size",
}
_CACHE_GENERIC_TOKENS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "get", "got",
    "had", "has", "have", "how", "i", "in", "into", "is", "it", "its",
    "make", "makes", "me", "my", "of", "on", "or", "our", "please",
    "should", "so", "that", "the", "their", "then", "there", "this", "to",
    "try", "use", "using", "was", "when", "which", "with", "would", "you",
    "your", "samsung", "galaxy", "screen", "display", "phone", "smartphone",
    "handset", "mobile", "tablet", "device", "app", "apps", "issue", "issues",
    "problem", "problems", "trouble", "troubleshooting", "settings", "help",
}

_FORM_FACTORS = {"foldable", "tablet", "wearable", "tv", "pc"}
_L2_TOP_K = 25


@dataclass(frozen=True)
class _ScenarioMetadata:
    """Generic identity and compatibility evidence for one cached response."""

    source_query: str
    scenario_representation: str
    title_representation: str
    symptom_families: frozenset[str]
    title_symptom_families: frozenset[str]
    action_symptom_families: frozenset[str]
    device_context: str
    device_families: frozenset[str]
    form_factor: frozenset[str]
    models: frozenset[str]


def _response_scenario_text(response: ContextDeeplinkResponse) -> tuple[str, str, str]:
    """Reconstruct a compact scenario/title representation from response fields."""
    titles: List[str] = []
    action_names: List[str] = []
    for context in response.contexts:
        titles.extend((context.title, context.goal))
        action_names.extend(action.actionName for action in context.actions)
    title_text = " ".join(value for value in titles if value)
    action_text = " ".join(value for value in action_names if value)
    representation = " ".join(value for value in (title_text, action_text) if value)
    return title_text, representation, action_text


def _build_scenario_metadata(
    query: str,
    response: ContextDeeplinkResponse,
    detector: DeviceDetector,
    device: str = "",
    model: str = "",
) -> _ScenarioMetadata:
    """Capture intent/device metadata at insertion without storing raw SIIS rows."""
    title_text, response_text, action_text = _response_scenario_text(response)
    device_context = " ".join(part for part in (device, model) if part)
    profile_context = " ".join(part for part in (query, device_context) if part)
    device_families, models = _explicit_device_profile(profile_context, detector)
    # A model may be stated by a response title even when the user's wording
    # omitted it. Do not infer form factor from broad titles like "phone or tablet".
    _, title_models = _explicit_device_profile(title_text, detector)
    all_models = frozenset(set(models) | title_models)
    symptoms = frozenset(_cache_symptom_families(query))
    title_symptoms = frozenset(_cache_symptom_families(title_text))
    action_symptoms = frozenset(_cache_symptom_families(action_text))
    representation = " ".join(part for part in (query, response_text) if part)
    return _ScenarioMetadata(
        source_query=query,
        scenario_representation=representation,
        title_representation=response_text,
        symptom_families=symptoms,
        title_symptom_families=title_symptoms,
        action_symptom_families=action_symptoms,
        device_context=device_context,
        device_families=frozenset(device_families),
        form_factor=frozenset(device_families & _FORM_FACTORS),
        models=all_models,
    )


def _cache_symptom_families(text: str) -> set[str]:
    """Extracts broad troubleshooting and task families from query text."""
    normalized = normalize_query(text)
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    families = set()
    for family, terms in _CACHE_SYMPTOM_TERMS.items():
        if terms & tokens:
            families.add(family)

    # A crease can be normal on a foldable display. Treat it as damage only
    # when the surrounding wording describes a physical defect or failure.
    if "crease" in tokens and tokens & {
        "crack", "cracked", "fracture", "fractured", "damage", "damaged",
        "broken", "failure", "failed",
    }:
        families.add("damage")

    # Distortion/artifact terms describe display symptoms only in a display
    # context; the same words can occur in unrelated app or media reports.
    if tokens & {"distorted", "distortion", "artifact", "artifacts", "glitch", "glitches"} and tokens & {
        "screen", "display", "panel", "image", "graphics",
    }:
        families.add("display_distortion")

    # "Transient" is broad on its own; in a rapid visual context it describes
    # the same intermittent display symptom as a flash or flicker.
    if "transient" in tokens and tokens & {"rapid", "flash", "flicker", "blink", "strobe"} and tokens & {
        "screen", "display", "panel", "image",
    }:
        families.add("display_flicker")

    # "Partial" describes scale only alongside an explicit size/scale cue;
    # in phrases such as partial illumination it describes a display failure.
    if "partial" in tokens and tokens & {
        "tiny", "small", "portion", "reduced", "shrink", "shrunken",
        "minimized", "scale", "scaling", "zoom", "size",
    }:
        families.add("display_size")

    # Bare "split" and "icons" commonly describe a damaged/partly dark panel.
    # Treat split as multitasking only when the text also names an app/window
    # task and does not describe a display failure.
    task_cues = {"app", "apps", "window", "windows", "multiwindow", "multitasking"}
    failure_cues = {
        "black", "dark", "half", "partial", "crack", "cracked", "broken",
        "failure", "failed", "unresponsive", "touch",
    }
    if "split" in tokens and tokens & task_cues and not tokens & failure_cues:
        families.add("multitasking")

    # A carrier/network switch is not a data-transfer intent. Preserve the
    # established device/data switching meaning when those entities are named.
    if "switch" in tokens and tokens & {"smart", "data", "file", "files", "phone", "device"}:
        if not tokens & {"carrier", "network", "service"}:
            families.add("transfer")
    if tokens & {"carrier", "network", "service"} and not tokens & {
        "data", "file", "files", "backup", "smart",
    }:
        families.discard("transfer")
    return families


def _meaningful_cache_tokens(text: str, families: set[str]) -> set[str]:
    """Returns non-generic lexical evidence plus normalized symptom entities."""
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", normalize_query(text))
        if len(token) > 1 and token not in _CACHE_GENERIC_TOKENS
    }
    tokens.update(f"symptom:{family}" for family in families)
    return tokens


def _model_identity(model: str) -> str:
    """Normalizes equivalent model spellings while preserving model numbers."""
    normalized = re.sub(r"[^a-z0-9]+", "", model.lower())
    normalized = normalized.replace("galaxy", "").replace("samsung", "")
    if normalized.startswith("z") and normalized[1:2].isalpha():
        normalized = normalized[1:]
    return normalized


def _explicit_device_profile(text: str, detector: DeviceDetector) -> tuple[set[str], set[str]]:
    """Detects stated device families, excluding the detector's screen default."""
    context = detector.detect(text)
    families = set(context.families)
    stated_smartphone = bool(
        re.search(
            r"\b(phone|smartphone|handset|galaxy\s*s\d{1,2}|galaxy\s*a\d{2,3})\b",
            text,
            re.IGNORECASE,
        )
    )
    if "smartphone" in families and not stated_smartphone:
        families.discard("smartphone")
    # Foldables are a phone form factor, so they are compatible with a generic
    # smartphone mention while remaining distinct from tablets and peripherals.
    if "foldable" in families:
        families.add("smartphone")
    models = {_model_identity(model) for model in context.models if _model_identity(model)}
    # DeviceDetector returns the first alternative from a model pattern. Keep
    # every explicitly stated model in slash-separated variants such as A15/A16.
    for match in re.finditer(
        r"\b(?:galaxy\s*)?[as]\d{2,3}(?:\s*/\s*(?:galaxy\s*)?[as]\d{2,3})+\b",
        text,
        re.IGNORECASE,
    ):
        for model in re.findall(r"(?:galaxy\s*)?([as]\d{2,3})", match.group(0), re.IGNORECASE):
            identity = _model_identity(model)
            if identity:
                models.add(identity)
    return families, models


def _scenario_feature_text(metadata: _ScenarioMetadata) -> str:
    """Build the generic L2 document from cached scenario evidence."""
    # Preserve composite scenario evidence across the canonical query, response
    # title/goal, and extracted action names. Hard compatibility continues to
    # use the canonical query independently.
    families = (
        metadata.symptom_families
        | metadata.title_symptom_families
        | metadata.action_symptom_families
    )
    family_features = " ".join(f"symptomfamily{family}" for family in sorted(families))
    return " ".join(
        part
        for part in (metadata.source_query, metadata.scenario_representation, family_features)
        if part
    )


def _query_feature_text(query: str) -> str:
    """Add the same normalized symptom-family features used by scenario docs."""
    families = _cache_symptom_families(query)
    family_features = " ".join(f"symptomfamily{family}" for family in sorted(families))
    return " ".join(part for part in (query, family_features) if part)


def _l2_compatible(
    query: str,
    candidate_query: str,
    detector: DeviceDetector,
    query_device: str = "",
    query_model: str = "",
    candidate_device: str = "",
) -> bool:
    """Requires symptom, device, and meaningful lexical compatibility."""
    query_context = " ".join(part for part in (query, query_device, query_model) if part)
    candidate_context = " ".join(part for part in (candidate_query, candidate_device) if part)

    query_families, query_models = _explicit_device_profile(query_context, detector)
    candidate_families, candidate_models = _explicit_device_profile(candidate_context, detector)
    if query_families and candidate_families and query_families.isdisjoint(candidate_families):
        return False
    if query_models and candidate_models and query_models.isdisjoint(candidate_models):
        return False

    query_symptoms = _cache_symptom_families(query)
    candidate_symptoms = _cache_symptom_families(candidate_query)
    shared_symptoms = query_symptoms & candidate_symptoms
    query_primary = query_symptoms & _PRIMARY_CACHE_SYMPTOMS
    candidate_primary = candidate_symptoms & _PRIMARY_CACHE_SYMPTOMS

    # A primary symptom must be represented in the cached scenario. If the
    # user states a distinctive task (email, transfer, multitasking, etc.),
    # that intent must also be present; a generic shared "black screen" term
    # cannot make those scenarios interchangeable.
    if query_primary and not (query_primary & candidate_primary):
        return False
    if query_symptoms and not shared_symptoms:
        return False
    query_distinctive = query_symptoms & _DISTINCTIVE_CACHE_SYMPTOMS
    if query_distinctive and not (query_distinctive & candidate_symptoms):
        return False

    # Display scaling and text magnification share size vocabulary but are
    # different intents when only one side identifies text size.
    if (
        "display_size" in query_symptoms
        and "text_size" in candidate_symptoms
        and "text_size" not in query_symptoms
    ):
        return False

    query_tokens = _meaningful_cache_tokens(query, query_symptoms)
    candidate_tokens = _meaningful_cache_tokens(candidate_query, candidate_symptoms)
    return bool(query_tokens & candidate_tokens)


class SemanticCache:
    """Dual-tier fast-path semantic cache for troubleshooting responses."""

    def __init__(self, similarity_threshold: float = 0.40):
        self.similarity_threshold = similarity_threshold
        # L1: normalized_query -> ContextDeeplinkResponse
        self._exact_cache: Dict[str, ContextDeeplinkResponse] = {}
        # L2: list of raw queries and responses
        self._cached_queries: List[str] = []
        self._cached_responses: List[ContextDeeplinkResponse] = []
        self._cached_device_contexts: List[str] = []
        self._candidate_group_ids: List[int] = []
        self._scenario_metadata: List[_ScenarioMetadata] = []
        self._device_detector = DeviceDetector()
        # Dynamic vectorizer for L2
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix: Optional[np.ndarray] = None
        self._title_vectorizer: Optional[TfidfVectorizer] = None
        self._title_tfidf_matrix: Optional[np.ndarray] = None
        self._rebuild_needed: bool = False

        # Metrics tracking
        self.total_requests = 0
        self.l1_hits = 0
        self.l2_hits = 0
        self.l2_compatibility_rejections = 0
        self.l2_candidates_evaluated = 0
        self.l2_rejection_reasons: Dict[str, int] = {}
        self.misses = 0
        self.latencies_ms: List[float] = []

    def get(
        self,
        query: str,
        device: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Tuple[Optional[ContextDeeplinkResponse], bool, float]:
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

        if (
            self._vectorizer is not None
            and self._tfidf_matrix is not None
            and self._title_vectorizer is not None
            and self._title_tfidf_matrix is not None
            and self._cached_queries
        ):
            query_vec = self._vectorizer.transform([norm])
            sims = cosine_similarity(query_vec, self._tfidf_matrix)[0]
            title_query_vec = self._title_vectorizer.transform([_query_feature_text(norm)])
            title_sims = cosine_similarity(
                title_query_vec, self._title_tfidf_matrix
            )[0]
            # Several stored variations can refer to one scenario. Keep that
            # scenario's strongest representation so aliases cannot crowd
            # distinct candidates out of the top-K search.
            best_by_group: Dict[int, Tuple[float, int]] = {}
            for idx, similarity in enumerate(sims):
                group_id = self._candidate_group_ids[idx]
                previous = best_by_group.get(group_id)
                if previous is None or float(similarity) > previous[0]:
                    best_by_group[group_id] = (float(similarity), idx)

            alias_top_groups = {
                group_id
                for group_id, _ in sorted(
                    best_by_group.items(),
                    key=lambda item: item[1][0],
                    reverse=True,
                )[:_L2_TOP_K]
            }
            scenario_top_groups = {
                group_id
                for group_id in sorted(
                    range(len(title_sims)),
                    key=lambda idx: (-float(title_sims[idx]), idx),
                )[:_L2_TOP_K]
            }
            # Keep candidates surfaced by either view: the raw query index
            # preserves the prior shortlist while the scenario index can find
            # paraphrases supported by title/goal/action and symptom metadata.
            candidate_group_ids = alias_top_groups | scenario_top_groups
            ranked_groups = sorted(
                (
                    (
                        group_id,
                        (
                            max(best_by_group[group_id][0], float(title_sims[group_id])),
                            best_by_group[group_id][1],
                        ),
                    )
                    for group_id in sorted(candidate_group_ids)
                ),
                key=lambda item: item[1][0],
                reverse=True,
            )
            compatible_candidates: List[Tuple[float, int]] = []
            for group_id, (semantic_score, entry_idx) in ranked_groups:
                if semantic_score < self.similarity_threshold:
                    break
                self.l2_candidates_evaluated += 1
                metadata = self._scenario_metadata[group_id]
                compatible, symptom_score, device_score = self._candidate_compatibility(
                    query=query,
                    device=device or "",
                    model=model or "",
                    metadata=metadata,
                )
                if not compatible:
                    self.l2_compatibility_rejections += 1
                    reasons = self._candidate_rejection_reasons(
                        query=query,
                        device=device or "",
                        model=model or "",
                        metadata=metadata,
                    )
                    for reason in reasons or {"unspecified_compatibility_failure"}:
                        self.l2_rejection_reasons[reason] = (
                            self.l2_rejection_reasons.get(reason, 0) + 1
                        )
                    continue

                combined_score = (
                    0.72 * semantic_score
                    + 0.18 * symptom_score
                    + 0.10 * device_score
                )
                compatible_candidates.append((combined_score, entry_idx))

            if compatible_candidates:
                _, matched_idx = max(compatible_candidates, key=lambda item: item[0])
                matched_response = self._cached_responses[matched_idx]
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

    def _candidate_rejection_reasons(
        self,
        *,
        query: str,
        device: str,
        model: str,
        metadata: _ScenarioMetadata,
    ) -> set[str]:
        """Explain the existing hard compatibility rejection for diagnostics.

        This mirrors the compatibility guard's predicates and is called only
        after the guard has already rejected a candidate; it never affects the
        matching decision.
        """
        reasons: set[str] = set()
        query_context = " ".join(part for part in (query, device, model) if part)
        candidate_context = " ".join(
            part for part in (metadata.source_query, metadata.device_context) if part
        )
        query_device_families, query_models = _explicit_device_profile(
            query_context, self._device_detector
        )
        candidate_device_families, candidate_models = _explicit_device_profile(
            candidate_context, self._device_detector
        )
        if (
            query_device_families
            and candidate_device_families
            and query_device_families.isdisjoint(candidate_device_families)
        ):
            reasons.add("device_family_mismatch")
        if query_models and candidate_models and query_models.isdisjoint(candidate_models):
            reasons.add("model_mismatch")

        query_symptoms = _cache_symptom_families(query)
        candidate_symptoms = _cache_symptom_families(metadata.source_query)
        shared_symptoms = query_symptoms & candidate_symptoms
        query_primary = query_symptoms & _PRIMARY_CACHE_SYMPTOMS
        candidate_primary = candidate_symptoms & _PRIMARY_CACHE_SYMPTOMS
        if query_primary and not (query_primary & candidate_primary):
            reasons.add("primary_symptom_family_mismatch")
        if query_symptoms and not shared_symptoms:
            reasons.add("symptom_family_mismatch")
        query_distinctive = query_symptoms & _DISTINCTIVE_CACHE_SYMPTOMS
        if query_distinctive and not (query_distinctive & candidate_symptoms):
            reasons.add("distinctive_intent_mismatch")
        if (
            "display_size" in query_symptoms
            and "text_size" in candidate_symptoms
            and "text_size" not in query_symptoms
        ):
            reasons.add("display_size_text_size_conflict")

        query_tokens = _meaningful_cache_tokens(query, query_symptoms)
        candidate_tokens = _meaningful_cache_tokens(
            metadata.source_query, candidate_symptoms
        )
        if not (query_tokens & candidate_tokens):
            reasons.add("meaningful_token_overlap_missing")

        query_device_families, query_models = _explicit_device_profile(
            query_context, self._device_detector
        )
        if query_models and metadata.models and query_models.isdisjoint(metadata.models):
            reasons.add("model_mismatch")
        return reasons

    def metrics_snapshot(self) -> Dict[str, Any]:
        """Return a copy of aggregate cache telemetry counters."""
        return {
            "l1_exact_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "l2_candidates_evaluated": self.l2_candidates_evaluated,
            "l2_candidates_rejected": self.l2_compatibility_rejections,
            "l2_rejection_reasons": dict(self.l2_rejection_reasons),
            "total_cache_misses": self.misses,
        }

    def _candidate_compatibility(
        self,
        *,
        query: str,
        device: str,
        model: str,
        metadata: _ScenarioMetadata,
    ) -> Tuple[bool, float, float]:
        """Return hard compatibility plus soft symptom/device agreement scores."""
        compatible = _l2_compatible(
            query=query,
            candidate_query=metadata.source_query,
            detector=self._device_detector,
            query_device=device,
            query_model=model,
            candidate_device=metadata.device_context,
        )
        query_device_context = " ".join(part for part in (query, device, model) if part)
        query_families, query_models = _explicit_device_profile(
            query_device_context, self._device_detector
        )

        # A model captured from a response title is also authoritative when
        # available, even if the cached source query omitted the model name.
        if query_models and metadata.models and query_models.isdisjoint(metadata.models):
            compatible = False

        query_symptoms = _cache_symptom_families(query)
        canonical_shared = query_symptoms & metadata.symptom_families
        title_shared = query_symptoms & metadata.title_symptom_families
        if query_symptoms:
            canonical_score = len(canonical_shared) / len(query_symptoms)
            title_score = len(title_shared) / len(query_symptoms)
            symptom_score = 0.80 * canonical_score + 0.20 * title_score
        else:
            query_tokens = _meaningful_cache_tokens(query, set())
            candidate_tokens = _meaningful_cache_tokens(
                metadata.scenario_representation,
                set(metadata.symptom_families | metadata.title_symptom_families),
            )
            symptom_score = len(query_tokens & candidate_tokens) / max(1, len(query_tokens))

        if query_models:
            device_score = 1.0 if query_models & metadata.models else 0.55
        elif query_families:
            device_score = 1.0 if query_families & metadata.device_families else 0.55
        else:
            device_score = 0.5
        return compatible, symptom_score, device_score

    def put(
        self,
        query: str,
        response: ContextDeeplinkResponse,
        variations: Optional[List[str]] = None,
        *,
        device: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Stores a query and its response in the cache, along with any known variations."""
        norm = normalize_query(query)
        if not norm:
            return

        self._exact_cache[norm] = response
        device_context = " ".join(part for part in (device, model) if part)
        metadata = _build_scenario_metadata(
            query=query,
            response=response,
            detector=self._device_detector,
            device=device or "",
            model=model or "",
        )
        group_id = len(self._scenario_metadata)
        self._scenario_metadata.append(metadata)

        def append_entry(entry_query: str) -> None:
            self._cached_queries.append(entry_query)
            self._cached_responses.append(response)
            self._cached_device_contexts.append(device_context)
            self._candidate_group_ids.append(group_id)

        append_entry(norm)

        if variations:
            for v in variations:
                v_norm = normalize_query(v)
                if v_norm:
                    self._exact_cache[v_norm] = response
                    append_entry(v_norm)

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
        # Maintain query-alias similarity and an independent scenario space.
        # The latter includes canonical query/title/goal/action evidence and
        # symptom-family features, allowing evidence to contribute before the
        # unchanged global threshold and compatibility gate.
        self._tfidf_matrix = self._vectorizer.fit_transform(self._cached_queries)
        self._title_vectorizer = TfidfVectorizer(
            ngram_range=(1, 1), stop_words="english", sublinear_tf=True
        )
        scenario_documents = [
            _scenario_feature_text(metadata) for metadata in self._scenario_metadata
        ]
        self._title_tfidf_matrix = self._title_vectorizer.fit_transform(scenario_documents)
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
