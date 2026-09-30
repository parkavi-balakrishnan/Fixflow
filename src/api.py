"""FixFlow REST API.

Provides:
- GET /health: Gate G2 health check returning {"status": "ok"}
- POST /v1/troubleshoot: Pure JSON endpoint returning ContextDeeplinkResponse
"""
from contextlib import asynccontextmanager
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.config import API_TITLE, API_VERSION, MAX_QUERY_LENGTH
from src.engine.pipeline import FixFlowPipeline
from src.engine.validator import detect_url_leakage, validate_response
from src.schema import ContextDeeplinkResponse

logger = logging.getLogger("fixflow.api")

# Global pipeline instance
_pipeline: Optional[FixFlowPipeline] = None


def get_pipeline() -> FixFlowPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FixFlowPipeline(prewarm=True)
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm pipeline and cache at startup
    pipeline = get_pipeline()
    logger.info("FixFlow pipeline initialized and prewarmed.")
    yield
    logger.info("FixFlow API shutting down.")


app = FastAPI(
    title=API_TITLE,
    description="Samsung PRISM Hackathon 2026 Theme 2 Smart Guided Troubleshooting Implementation",
    version=API_VERSION,
    lifespan=lifespan,
)


class SIISResponsePayload(BaseModel):
    title: Optional[str] = ""
    content: Optional[str] = ""


class TroubleshootRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language troubleshooting query")
    siis_response: Optional[SIISResponsePayload] = Field(
        None, description="Pre-cleaned SIIS knowledge store response payload"
    )
    device: Optional[str] = Field(
        None, description="Optional device name or form factor (e.g. Galaxy S24, Tablet, Watch)"
    )
    model: Optional[str] = Field(
        None, description="Optional specific device model name"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query cannot be empty or whitespace only")
        if len(stripped) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query length exceeds maximum limit of {MAX_QUERY_LENGTH} characters")
        return stripped

    @field_validator("device", "model")
    @classmethod
    def sanitize_optional_str(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        return stripped[:200]


class HealthResponse(BaseModel):
    status: str = "ok"


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Gate G2 health check endpoint."""
    return HealthResponse(status="ok")


@app.post(
    "/v1/troubleshoot",
    response_model=ContextDeeplinkResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def troubleshoot_endpoint(
    req: TroubleshootRequest,
    response: Response,
) -> ContextDeeplinkResponse:
    """Processes user query and returns a structured, deeplink-enriched ContextDeeplinkResponse."""
    pipeline = get_pipeline()

    siis_dict = None
    if req.siis_response:
        siis_dict = req.siis_response.model_dump()

    try:
        result, telemetry = pipeline.troubleshoot(
            req.query,
            siis_dict,
            device=req.device,
            model=req.model,
        )
    except Exception as e:
        logger.error(f"Pipeline troubleshooting error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Troubleshooting engine error: {str(e)}",
        )

    # Attach telemetry headers for performance tracking and observability
    response.headers["X-Cache-Hit"] = str(telemetry.get("cache_hit", False)).lower()
    response.headers["X-Latency-Ms"] = str(telemetry.get("latency_ms", 0.0))
    response.headers["X-Source"] = str(telemetry.get("source", "unknown"))
    if "retrieval_latency_ms" in telemetry:
        response.headers["X-Retrieval-Latency-Ms"] = str(telemetry.get("retrieval_latency_ms", 0.0))
        response.headers["X-Retrieval-Score"] = str(telemetry.get("retrieval_score", 0.0))
        response.headers["X-Retrieved-Doc-Id"] = str(telemetry.get("retrieved_doc_id", ""))

    # Gate & Validation observability headers
    val_res = validate_response(result)
    response.headers["X-Response-Valid"] = str(val_res.is_valid).lower()

    # Gate G5 URL leak verification
    raw_json = result.model_dump_json()
    leaks = detect_url_leakage(raw_json)
    response.headers["X-Gate-G5-Clean"] = "true" if len(leaks) == 0 else "false"

    return result
