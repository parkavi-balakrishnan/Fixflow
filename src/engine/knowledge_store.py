"""Knowledge Base Storage & Indexing Engine for FixFlow.

Manages persistent storage, loading, and memory indexing of processed
Samsung troubleshooting knowledge documents.

Separation of Concerns:
- Raw Data: data/siis_responses.json (completely unchanged)
- Processed Knowledge: data/processed_knowledge/processed_siis.json
- In-memory Indexing: Fast lookups by doc_id, category, and device model.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional

from src.engine.preprocessor import KnowledgeDocument, SIISPreprocessor

DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)


class KnowledgeStore:
    """Manages processed troubleshooting documents and indexes."""

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self.data_dir = data_dir
        self.raw_path = os.path.join(data_dir, "siis_responses.json")
        self.processed_dir = os.path.join(data_dir, "processed_knowledge")
        self.processed_path = os.path.join(self.processed_dir, "processed_siis.json")

        self.preprocessor = SIISPreprocessor()
        self.documents: List[KnowledgeDocument] = []
        self._doc_map: Dict[str, KnowledgeDocument] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._model_index: Dict[str, List[str]] = {}

        self.load_or_build()

    def load_or_build(self, force_rebuild: bool = False) -> int:
        """Loads processed documents from disk or builds them from raw SIIS file."""
        need_rebuild = force_rebuild or not os.path.exists(self.processed_path)

        if not need_rebuild and os.path.exists(self.raw_path):
            # Check timestamps
            if os.path.getmtime(self.raw_path) > os.path.getmtime(self.processed_path):
                need_rebuild = True

        if need_rebuild:
            self.rebuild_from_raw()
        else:
            self.documents = self.preprocessor.load_processed(self.processed_path)
            self._build_in_memory_indexes()

        return len(self.documents)

    def rebuild_from_raw(self) -> int:
        """Reads raw siis_responses.json, processes knowledge, and saves to processed_path."""
        if not os.path.exists(self.raw_path):
            return 0

        with open(self.raw_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        raw_responses = raw_data.get("responses", [])
        self.documents = self.preprocessor.process_all(raw_responses)
        self.preprocessor.save_processed(self.documents, self.processed_path)
        self._build_in_memory_indexes()
        return len(self.documents)

    def _build_in_memory_indexes(self) -> None:
        """Constructs fast lookup indices over documents."""
        self._doc_map.clear()
        self._category_index.clear()
        self._model_index.clear()

        for doc in self.documents:
            self._doc_map[doc.doc_id] = doc

            # Index by category
            for cat in doc.device_categories:
                cat_lower = cat.lower()
                self._category_index.setdefault(cat_lower, []).append(doc.doc_id)

            # Index by detected device models
            for model in doc.device_models:
                m_lower = model.lower()
                self._model_index.setdefault(m_lower, []).append(doc.doc_id)

    def get_document(self, doc_id: str) -> Optional[KnowledgeDocument]:
        """Retrieves a document by its ID in O(1) time."""
        return self._doc_map.get(doc_id)

    def get_documents_by_category(self, category: str) -> List[KnowledgeDocument]:
        """Retrieves all documents associated with a device category."""
        doc_ids = self._category_index.get(category.lower(), [])
        return [self._doc_map[did] for did in doc_ids if did in self._doc_map]

    def count(self) -> int:
        """Returns total number of indexed knowledge documents."""
        return len(self.documents)
