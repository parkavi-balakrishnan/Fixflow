/**
 * Type definitions matching the FixFlow backend FastAPI schemas (src/schema.py & src/api.py).
 */

export type Condition = 'greater' | 'equal' | 'less';

export type ResultTypes = 'boolean' | 'integer' | 'str' | 'float';

export type ActionCategory = 'auto' | 'manual' | 'critical';

export interface BaseDeeplink {
  deeplink: string;
}

export interface Deeplink extends BaseDeeplink {
  description: string;
  message?: string;
  classes?: Record<string, string> | null;
  originalType?: string | null;
}

export interface ValidationDeepLink extends BaseDeeplink {
  key: string;
  resultType?: ResultTypes | null;
  condition?: Condition | null;
  value?: string | null;
}

export interface StepGroup {
  steps: string[];
  validationDeeplink?: ValidationDeepLink | null;
  actionableDeeplink?: Deeplink | null;
}

export interface Action {
  actionName: string;
  description: string;
  stepGroups: StepGroup[];
  category?: ActionCategory;
}

export interface Goal {
  goal: string;
  title: string;
  actions: Action[];
  score: number;
}

export interface ContextDeeplinkResponse {
  contexts: Goal[];
}

export interface SIISResponsePayload {
  title?: string;
  content?: string;
}

export interface TroubleshootRequest {
  query: string;
  device?: string;
  model?: string;
  siis_response?: SIISResponsePayload;
}

export interface HealthResponse {
  status: string;
}

export interface TroubleshootingTelemetry {
  cacheHit?: boolean;
  latencyMs?: number;
  source?: string;
  retrievalLatencyMs?: number;
  retrievalScore?: number;
  retrievedDocId?: string;
  responseValid?: boolean;
  gateG5Clean?: boolean;
}

export interface TroubleshootingResultData {
  response: ContextDeeplinkResponse;
  telemetry: TroubleshootingTelemetry;
  submittedQuery: string;
  submittedDevice?: string;
  submittedModel?: string;
}

export type ErrorType = 'network' | 'validation' | 'server' | 'empty' | 'unknown';

export interface FixFlowError {
  type: ErrorType;
  title: string;
  message: string;
  detail?: string;
  statusCode?: number;
}
