"""FixFlow REST API.

Provides:
- GET /health: Gate G2 health check returning {"status": "ok"}
- POST /v1/troubleshoot: Pure JSON endpoint returning ContextDeeplinkResponse
"""
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from src.engine.pipeline import FixFlowPipeline
from src.schema import ContextDeeplinkResponse

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
    get_pipeline()
    yield


app = FastAPI(
    title="FixFlow Smart Guided Troubleshooting Engine",
    description="Samsung PRISM Hackathon 2026 Theme 2 Implementation",
    version="1.0.0",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Troubleshooting engine error: {str(e)}",
        )

    # Attach telemetry headers for performance tracking
    response.headers["X-Cache-Hit"] = str(telemetry.get("cache_hit", False)).lower()
    response.headers["X-Latency-Ms"] = str(telemetry.get("latency_ms", 0.0))
    response.headers["X-Source"] = str(telemetry.get("source", "unknown"))
    if "retrieval_latency_ms" in telemetry:
        response.headers["X-Retrieval-Latency-Ms"] = str(telemetry.get("retrieval_latency_ms", 0.0))
        response.headers["X-Retrieval-Score"] = str(telemetry.get("retrieval_score", 0.0))
        response.headers["X-Retrieved-Doc-Id"] = str(telemetry.get("retrieved_doc_id", ""))

    return result
