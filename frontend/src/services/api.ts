import type {
  ContextDeeplinkResponse,
  FixFlowError,
  HealthResponse,
  TroubleshootRequest,
  TroubleshootingResultData,
  TroubleshootingTelemetry,
} from '../types/fixflow';

// Base API URL configured via environment variable
const RAW_API_URL = import.meta.env.VITE_API_URL || '';
const API_BASE_URL = RAW_API_URL.replace(/\/+$/, '');

/**
 * Extracts telemetry headers attached by src/api.py
 */
function extractTelemetry(headers: Headers): TroubleshootingTelemetry {
  const cacheHitHeader = headers.get('x-cache-hit');
  const latencyHeader = headers.get('x-latency-ms');
  const sourceHeader = headers.get('x-source');
  const retrievalLatencyHeader = headers.get('x-retrieval-latency-ms');
  const retrievalScoreHeader = headers.get('x-retrieval-score');
  const retrievedDocIdHeader = headers.get('x-retrieved-doc-id');
  const responseValidHeader = headers.get('x-response-valid');
  const gateG5CleanHeader = headers.get('x-gate-g5-clean');

  return {
    cacheHit: cacheHitHeader ? cacheHitHeader.toLowerCase() === 'true' : undefined,
    latencyMs: latencyHeader ? parseFloat(latencyHeader) : undefined,
    source: sourceHeader || undefined,
    retrievalLatencyMs: retrievalLatencyHeader ? parseFloat(retrievalLatencyHeader) : undefined,
    retrievalScore: retrievalScoreHeader ? parseFloat(retrievalScoreHeader) : undefined,
    retrievedDocId: retrievedDocIdHeader || undefined,
    responseValid: responseValidHeader ? responseValidHeader.toLowerCase() === 'true' : undefined,
    gateG5Clean: gateG5CleanHeader ? gateG5CleanHeader.toLowerCase() === 'true' : undefined,
  };
}

/**
 * Formats FastAPI validation error details into a readable string
 */
function formatValidationErrors(errorDetail: unknown): string {
  if (typeof errorDetail === 'string') {
    return errorDetail;
  }
  if (Array.isArray(errorDetail)) {
    return errorDetail
      .map((item) => {
        if (typeof item === 'object' && item !== null && 'msg' in item) {
          const loc = Array.isArray(item.loc) ? item.loc.slice(1).join(' -> ') : '';
          return loc ? `${loc}: ${item.msg}` : (item.msg as string);
        }
        return JSON.stringify(item);
      })
      .join(', ');
  }
  return 'Invalid query parameters submitted.';
}

/**
 * Executes fetch with automatic fallback to Vite proxy if cross-origin fetch fails
 */
async function fetchWithFallback(
  path: string,
  options: RequestInit
): Promise<Response> {
  const targetUrl = API_BASE_URL ? `${API_BASE_URL}${path}` : path;

  try {
    const response = await fetch(targetUrl, options);
    return response;
  } catch (err) {
    // If a configured absolute URL failed (e.g. CORS preflight blocked by FastAPI or connection refused),
    // and path is relative, attempt the local Vite proxy path if different.
    if (API_BASE_URL && API_BASE_URL.startsWith('http')) {
      try {
        console.warn(`Direct fetch to ${targetUrl} failed, falling back to Vite dev proxy ${path}...`);
        const fallbackResponse = await fetch(path, options);
        return fallbackResponse;
      } catch {
        throw err;
      }
    }
    throw err;
  }
}

/**
 * Checks backend health via GET /health
 */
export async function checkBackendHealth(): Promise<HealthResponse> {
  try {
    const res = await fetchWithFallback('/health', {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      throw new Error(`Health check returned status ${res.status}`);
    }

    return (await res.json()) as HealthResponse;
  } catch (err) {
    throw {
      type: 'network',
      title: 'Backend Unavailable',
      message: 'Could not connect to the FixFlow health endpoint.',
      detail: err instanceof Error ? err.message : String(err),
    } as FixFlowError;
  }
}

/**
 * Sends a natural language troubleshooting query to POST /v1/troubleshoot
 */
export async function troubleshoot(
  request: TroubleshootRequest
): Promise<TroubleshootingResultData> {
  const payload: Record<string, unknown> = {
    query: request.query.trim(),
  };

  if (request.device?.trim()) {
    payload.device = request.device.trim();
  }
  if (request.model?.trim()) {
    payload.model = request.model.trim();
  }
  if (request.siis_response) {
    payload.siis_response = request.siis_response;
  }

  let response: Response;
  try {
    response = await fetchWithFallback('/v1/troubleshoot', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw {
      type: 'network',
      title: 'Connection Failed',
      message: 'Unable to reach the FixFlow troubleshooting service.',
      detail:
        'Please check that the FastAPI backend server is running on http://127.0.0.1:8000 and accessible.',
    } as FixFlowError;
  }

  // Handle HTTP status codes
  if (response.status === 422) {
    let errorDetail = 'Validation error occurred';
    try {
      const errJson = await response.json();
      errorDetail = formatValidationErrors(errJson.detail);
    } catch {
      // ignore json parse error
    }
    throw {
      type: 'validation',
      title: 'Invalid Request',
      message: errorDetail,
      statusCode: 422,
    } as FixFlowError;
  }

  if (response.status >= 500) {
    let errorDetail = 'Internal server error';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // ignore
    }
    throw {
      type: 'server',
      title: 'Troubleshooting Engine Error',
      message: 'The troubleshooting service encountered an unexpected error.',
      detail: errorDetail,
      statusCode: response.status,
    } as FixFlowError;
  }

  if (!response.ok) {
    throw {
      type: 'unknown',
      title: 'Unexpected Response',
      message: `The server returned an unexpected status code: ${response.status}`,
      statusCode: response.status,
    } as FixFlowError;
  }

  let data: ContextDeeplinkResponse;
  try {
    data = (await response.json()) as ContextDeeplinkResponse;
  } catch (err) {
    throw {
      type: 'unknown',
      title: 'Data Parsing Error',
      message: 'Failed to parse the server response into JSON.',
      detail: err instanceof Error ? err.message : String(err),
    } as FixFlowError;
  }

  // Check for empty results
  if (!data.contexts || data.contexts.length === 0) {
    throw {
      type: 'empty',
      title: 'No Troubleshooting Steps Found',
      message: "We couldn't find a reliable troubleshooting path for this scenario.",
      detail: 'Try adjusting the wording of your issue or specifying your device model.',
    } as FixFlowError;
  }

  // Extract telemetry headers
  const telemetry = extractTelemetry(response.headers);

  return {
    response: data,
    telemetry,
    submittedQuery: request.query.trim(),
    submittedDevice: request.device?.trim(),
    submittedModel: request.model?.trim(),
  };
}
