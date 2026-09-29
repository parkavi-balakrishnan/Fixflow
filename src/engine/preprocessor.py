"""SIIS Knowledge Base Data Preprocessing Engine for FixFlow.

Transforms raw Samsung SIIS (Samsung Internal Information Store) troubleshooting responses
into clean, structured, and searchable KnowledgeDocument objects for RAG retrieval.

Constraints:
- Preserves raw Samsung knowledge without fabricating troubleshooting steps.
- Extracts structured device categories, models, symptoms, and troubleshooting sections.
- Generates rich, normalized searchable text representations for hybrid search.
- Scalable toward 10K+ troubleshooting scenarios without hardcoded if/else rules.
"""
from dataclasses import asdict, dataclass, field
import json
import os
import re
from typing import Any, Dict, List, Optional, Set

# Comprehensive regex to strip web URLs, emails, domains, and links (Gate G5 alignment)
_URL_STRIP_REGEX = re.compile(
    r"\b(?:https?|ftp)://\S+"
    r"|\bwww\.\S+"
    r"|\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"
    r"|\b[a-zA-Z0-9-]+\.(?:com|org|net|io|edu|gov|co\.kr|co\.uk)(?:/[^\s<>'\"]*)?\b"
    r"|\[([^\]]+)\]\([^\)]+\)"
    r"|<[^>]+>",
    re.IGNORECASE,
)

# Common troubleshooting symptom keywords to extract
_SYMPTOM_PATTERNS = [
    r"\bblank\s+screen\b",
    r"\bblack\s+screen\b",
    r"\bblue\s+screen\b",
    r"\bwhite\s+screen\b",
    r"\bcracked\s+screen\b",
    r"\bbleeding\s+screen\b",
    r"\bflickers?\b",
    r"\bflashes?\b",
    r"\bdelayed\s+touch\b",
    r"\blaggy\b",
    r"\bresponsiveness\b",
    r"\bnot\s+turning\s+on\b",
    r"\bwon'?t\s+turn\s+on\b",
    r"\bwon'?t\s+start\b",
    r"\bliquid\s+damage\b",
    r"\bldi\b",
    r"\bforce\s+restart\b",
    r"\bsafe\s+mode\b",
    r"\bemail\s+server\b",
    r"\bgmail\b",
    r"\bsmart\s+switch\b",
    r"\btransfer\s+data\b",
    r"\bqr\s+code\b",
    r"\bmulti\s+window\b",
    r"\bapp\s+pairs?\b",
    r"\bfloating\s+circle\b",
    r"\bedge\s+panel\b",
    r"\bsplit\s+screen\b",
    r"\bpop-?up\s+view\b",
    r"\bscreen\s+mirroring\b",
    r"\bsmart\s+view\b",
    r"\bcasting\b",
    r"\btouchscreen\s+issues?\b",
    r"\bdoes\s+not\s+rotate\b",
    r"\bdistorted\b",
    r"\bhalf\s+black\b",
    r"\binner\s+screen\b",
    r"\bcover\s+screen\b",
    r"\bfingerprint\b",
    r"\bsecure\s+folder\b",
]

_COMPILED_SYMPTOMS = [re.compile(p, re.IGNORECASE) for p in _SYMPTOM_PATTERNS]

# Known Samsung device patterns
_DEVICE_REGEXES = [
    (r"\b(galaxy\s*s\d{1,2}(?:\s*ultra|\s*plus)?|s\*{3,5}\s*ultra)\b", "Galaxy S Series"),
    (r"\b(galaxy\s*z\s*flip\s*\d*|galaxy\s*flip\s*\d*|z\s*flip\s*\d*)\b", "Galaxy Z Flip"),
    (r"\b(galaxy\s*z\s*fold\s*\d*|galaxy\s*fold\s*\d*|z\s*fold\s*\d*|z\s*trifold)\b", "Galaxy Z Fold"),
    (r"\b(galaxy\s*a\d{2,3}[a-z]?|samsung\s*a\d{2,3}[a-z]?)\b", "Galaxy A Series"),
    (r"\b(galaxy\s*tab(?:\s*[a-z0-9]+)?|tablet|a115g\s*tablet)\b", "Galaxy Tab / Tablet"),
    (r"\b(galaxy\s*watch\s*\d*|wearable)\b", "Galaxy Watch / Wearable"),
    (r"\b(samsung\s*tv|smart\s*tv|qled|oled|lifestyle\s*tv)\b", "Samsung TV"),
    (r"\b(galaxy\s*book|notebook|windows\s*pc|computer)\b", "PC / Galaxy Book"),
]


def strip_urls(text: str) -> str:
    """Removes web links, markdown links, emails, and raw URLs."""
    if not text:
        return ""
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    cleaned = _URL_STRIP_REGEX.sub("", cleaned)
    return " ".join(cleaned.split())


@dataclass
class KnowledgeSection:
    """Represents a logical section within a troubleshooting document."""
    section_title: str
    steps: List[str] = field(default_factory=list)
    category: str = "manual"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_title": self.section_title,
            "steps": self.steps,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeSection":
        return cls(
            section_title=data.get("section_title", ""),
            steps=data.get("steps", []),
            category=data.get("category", "manual"),
        )


@dataclass
class KnowledgeDocument:
    """Structured, search-optimized representation of a Samsung SIIS response."""
    doc_id: str
    title: str
    original_query: str
    device_categories: List[str] = field(default_factory=list)
    device_models: List[str] = field(default_factory=list)
    symptoms: List[str] = field(default_factory=list)
    sections: List[KnowledgeSection] = field(default_factory=list)
    searchable_text: str = ""
    raw_siis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "original_query": self.original_query,
            "device_categories": self.device_categories,
            "device_models": self.device_models,
            "symptoms": self.symptoms,
            "sections": [s.to_dict() for s in self.sections],
            "searchable_text": self.searchable_text,
            "raw_siis": self.raw_siis,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeDocument":
        sections = [
            KnowledgeSection.from_dict(s) if isinstance(s, dict) else s
            for s in data.get("sections", [])
        ]
        return cls(
            doc_id=data.get("doc_id", ""),
            title=data.get("title", ""),
            original_query=data.get("original_query", ""),
            device_categories=data.get("device_categories", []),
            device_models=data.get("device_models", []),
            symptoms=data.get("symptoms", []),
            sections=sections,
            searchable_text=data.get("searchable_text", ""),
            raw_siis=data.get("raw_siis", {}),
        )


class SIISPreprocessor:
    """Parses raw SIIS responses into clean KnowledgeDocument objects."""

    def parse_categories(self, content: str) -> List[str]:
        """Extracts device categories from the SIIS header line (e.g. '( Smartphone,Others Mobile,Tablet )')."""
        if not content:
            return ["Smartphone", "Others Mobile"]

        first_line = content.split("\n")[0]
        # Look for category list in parentheses: e.g. ( Smartphone,Others Mobile,Tablet,Mobile Accessories)
        match = re.search(r"\(([^)]+)\):?", first_line)
        if match:
            cats = [c.strip() for c in match.group(1).split(",") if c.strip()]
            if cats:
                return cats

        # Fallback to comma-separated list before the first title keyword
        prefix = first_line.split(":")[0] if ":" in first_line else first_line
        cats = [c.strip() for c in prefix.split(",") if c.strip() and len(c.strip()) < 30]
        return cats or ["Smartphone"]

    def parse_sections(self, content: str, default_title: str = "Overview") -> List[KnowledgeSection]:
        """Extracts logical screen/step sections from raw markdown content without inventing steps."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if not lines:
            return []

        # Drop or split the header line if it contains the device categories prefix
        if re.search(r"\(([^)]+)\):?", lines[0]):
            header_match = re.search(r"\(([^)]+)\):?\s*(.*)", lines[0])
            rest_of_line = header_match.group(2).strip() if header_match else ""
            if rest_of_line:
                lines = [rest_of_line] + lines[1:]
            else:
                lines = lines[1:]

        sections: List[KnowledgeSection] = []
        current_title = default_title
        current_steps: List[str] = []

        for line in lines:
            # Check for markdown headers (# Title, ## Step 1: ..., ### Step 2: ...)
            header_match = re.match(r"^#{1,4}\s*(?:Step\s*\d+:?\s*)?(.*)", line, re.IGNORECASE)
            if header_match:
                if current_steps:
                    sections.append(
                        KnowledgeSection(
                            section_title=current_title,
                            steps=current_steps,
                            category=self._classify_category(current_title, current_steps),
                        )
                    )
                    current_steps = []
                new_title = header_match.group(1).strip()
                current_title = new_title if new_title else default_title
            else:
                # Clean line as step
                cleaned_line = strip_urls(line)
                step_text = re.sub(r"^[-*•\d.]+\s*", "", cleaned_line).strip()
                if len(step_text) > 8 and not step_text.lower().startswith("glossary"):
                    current_steps.append(step_text)

        if current_steps:
            sections.append(
                KnowledgeSection(
                    section_title=current_title,
                    steps=current_steps,
                    category=self._classify_category(current_title, current_steps),
                )
            )

        return sections

    def extract_device_mentions(self, text: str) -> List[str]:
        """Identifies specific Samsung models or device families mentioned in text."""
        devices: Set[str] = set()
        text_lower = text.lower()
        for pattern, label in _DEVICE_REGEXES:
            matches = re.findall(pattern, text_lower)
            for m in matches:
                devices.add(m.strip())
        return sorted(list(devices))

    def extract_symptoms(self, title: str, query: str, content: str = "") -> List[str]:
        """Extracts key symptom indicators from title, query, and content."""
        symptoms: Set[str] = set()
        combined = f"{title} {query} {content[:500]}".lower()

        for pattern in _COMPILED_SYMPTOMS:
            for match in pattern.findall(combined):
                symptoms.add(match.lower())

        return sorted(list(symptoms))

    def _classify_category(self, title: str, steps: List[str]) -> str:
        """Determines if a section is auto, manual, or critical."""
        combined = f"{title} {' '.join(steps)}".lower()
        if any(w in combined for w in ["restart", "reboot", "factory reset", "wipe", "safe mode"]):
            return "critical"
        if any(w in combined for w in ["settings", "tap", "turn on", "enable", "toggle", "switch"]):
            return "auto"
        return "manual"

    def process_item(self, item: Dict[str, Any]) -> KnowledgeDocument:
        """Transforms a single raw SIIS response item into a clean KnowledgeDocument."""
        doc_id = str(item.get("id", ""))
        original_query = str(item.get("original_query", "")).strip()
        raw_siis = item.get("siis_response", {}) or {}

        title = str(raw_siis.get("title", "")).strip()
        content = str(raw_siis.get("content", ""))

        categories = self.parse_categories(content)
        sections = self.parse_sections(content, default_title=title or "Troubleshooting Steps")
        device_models = self.extract_device_mentions(f"{title} {original_query} {content}")
        symptoms = self.extract_symptoms(title, original_query, content)

        # Assemble rich, clean searchable representation
        # Boosting title and symptom keywords for optimal retrieval
        section_titles = [s.section_title for s in sections]
        step_samples = []
        for s in sections[:4]:
            step_samples.extend(s.steps[:3])

        clean_query = original_query.lstrip("1234567890. \"'").rstrip("\"'")
        searchable_parts = [
            f"Title: {title}",
            f"Title: {title}",  # 2x title weight
            f"Query: {clean_query}",
            f"Categories: {' '.join(categories)}",
            f"Devices: {' '.join(device_models)}",
            f"Symptoms: {' '.join(symptoms)}",
            f"Sections: {' | '.join(section_titles)}",
            f"Steps: {' '.join(step_samples)}",
        ]
        searchable_text = "\n".join(searchable_parts)

        return KnowledgeDocument(
            doc_id=doc_id,
            title=title,
            original_query=original_query,
            device_categories=categories,
            device_models=device_models,
            symptoms=symptoms,
            sections=sections,
            searchable_text=searchable_text,
            raw_siis=raw_siis,
        )

    def process_all(self, raw_items: List[Dict[str, Any]]) -> List[KnowledgeDocument]:
        """Processes a list of raw SIIS response items into KnowledgeDocuments."""
        return [self.process_item(item) for item in raw_items]

    def save_processed(self, documents: List[KnowledgeDocument], output_path: str) -> None:
        """Serializes processed knowledge documents to a JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        data = {
            "_generator": "FixFlow SIISPreprocessor",
            "count": len(documents),
            "documents": [d.to_dict() for d in documents],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_processed(self, input_path: str) -> List[KnowledgeDocument]:
        """Loads processed knowledge documents from a JSON file."""
        if not os.path.exists(input_path):
            return []
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_docs = data.get("documents", [])
        return [KnowledgeDocument.from_dict(d) for d in raw_docs]
