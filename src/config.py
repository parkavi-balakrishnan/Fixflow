"""Lightweight configuration management for FixFlow.

Provides centralized paths, pipeline defaults, retrieval weights,
cache thresholds, and benchmark configuration with environment variable overrides.
"""
from dataclasses import dataclass, field
import os
from typing import Dict


# Root directories
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.getenv("FIXFLOW_DATA_DIR", os.path.join(REPO_ROOT, "data"))
ARTIFACTS_DIR = os.getenv("FIXFLOW_ARTIFACTS_DIR", os.path.join(REPO_ROOT, "artifacts"))

# Core dataset file paths
DEEPLINKS_PATH = os.path.join(DATA_DIR, "deeplinks.json")
SIIS_RESPONSES_PATH = os.path.join(DATA_DIR, "siis_responses.json")
INPUT_TXT_PATH = os.path.join(DATA_DIR, "input.txt")
SAMPLE_OUTPUT_PATH = os.path.join(DATA_DIR, "sample_output.json")
PROCESSED_KNOWLEDGE_DIR = os.path.join(DATA_DIR, "processed_knowledge")
PROCESSED_SIIS_PATH = os.path.join(PROCESSED_KNOWLEDGE_DIR, "processed_siis.json")

# Cache configuration
DEFAULT_CACHE_THRESHOLD: float = float(os.getenv("FIXFLOW_CACHE_THRESHOLD", "0.40"))
DEFAULT_CACHE_PREWARM: bool = os.getenv("FIXFLOW_CACHE_PREWARM", "true").lower() in ("1", "true", "yes")

# Retrieval configuration
DEFAULT_TOP_K: int = int(os.getenv("FIXFLOW_TOP_K", "3"))
DEFAULT_SEMANTIC_WEIGHT: float = float(os.getenv("FIXFLOW_SEMANTIC_WEIGHT", "0.40"))
DEFAULT_BM25_WEIGHT: float = float(os.getenv("FIXFLOW_BM25_WEIGHT", "0.35"))
DEFAULT_DEVICE_WEIGHT: float = float(os.getenv("FIXFLOW_DEVICE_WEIGHT", "0.25"))

# API & Security configuration
API_TITLE: str = "FixFlow Smart Guided Troubleshooting Engine"
API_VERSION: str = "1.0.0"
MAX_QUERY_LENGTH: int = int(os.getenv("FIXFLOW_MAX_QUERY_LENGTH", "2000"))
LOG_LEVEL: str = os.getenv("FIXFLOW_LOG_LEVEL", "INFO")

# Benchmark configuration
DEFAULT_RESULTS_JSONL: str = os.getenv("FIXFLOW_RESULTS_JSONL", os.path.join(REPO_ROOT, "results.jsonl"))
DEFAULT_REPORT_JSON: str = os.getenv("FIXFLOW_REPORT_JSON", os.path.join(REPO_ROOT, "benchmark_report.json"))
DEFAULT_REPORT_MD: str = os.getenv("FIXFLOW_REPORT_MD", os.path.join(REPO_ROOT, "benchmark_report.md"))


@dataclass
class FixFlowConfig:
    """Consolidated runtime configuration for FixFlow components."""
    data_dir: str = DATA_DIR
    deeplinks_path: str = DEEPLINKS_PATH
    siis_responses_path: str = SIIS_RESPONSES_PATH
    input_txt_path: str = INPUT_TXT_PATH
    sample_output_path: str = SAMPLE_OUTPUT_PATH
    processed_siis_path: str = PROCESSED_SIIS_PATH
    cache_threshold: float = DEFAULT_CACHE_THRESHOLD
    prewarm: bool = DEFAULT_CACHE_PREWARM
    top_k: int = DEFAULT_TOP_K
    max_query_length: int = MAX_QUERY_LENGTH
    log_level: str = LOG_LEVEL

    def to_dict(self) -> Dict[str, object]:
        return {
            "data_dir": self.data_dir,
            "cache_threshold": self.cache_threshold,
            "prewarm": self.prewarm,
            "top_k": self.top_k,
            "max_query_length": self.max_query_length,
            "log_level": self.log_level,
        }


def get_default_config() -> FixFlowConfig:
    """Returns the default FixFlow configuration instance."""
    return FixFlowConfig()
