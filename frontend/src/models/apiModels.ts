// API models for the CyberAgent frontend

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
}

export interface ModelStatusResponse {
  is_trained: boolean;
  model_type: string;
  feature_count: number;
  classes: string[];
  last_updated: string;
}

export interface PredictRequest {
  [key: string]: number | string | boolean;
}

export interface PredictResponse {
  predicted_class: string;
  confidence: number;
  class_probabilities: Record<string, number>;
}

export type FlowMetadataResponse = FlowRecord;

export interface GroundingCheck {
  passed: boolean;
  checks: Array<{ check: string; passed: boolean; detail: string }>;
  ungrounded_numbers: string[];
}

/** Connection-level fields of a flow, as stored in the flow record (GET /flow/{id}). */
export interface FlowRecord {
  flow_id: number | null;
  source_ip: string | null;
  source_port: number | null;
  destination_ip: string | null;
  destination_port: number | null;
  protocol: string | null;
  timestamp: string | null;
  /** Fields the dataset does not keep; the UI says "not in the record" for these. */
  missing_fields: string[];
  available: boolean;
  reason?: string | null;
}

export interface ShapFeature {
  feature: string;
  shap_value: number;
  /** The served row is post-scaler, so this is a z-score, not a packet count. */
  standardized_value: number;
}

export interface ShapExplanation {
  predicted_class: string | null;
  value_scale: string | null;
  features: ShapFeature[] | null;
  explanation_error: string | null;
}

export interface InvestigationResult {
  verdict: string;
  predicted_class: string;
  severity: string;
  confidence: number;
  needs_human_review: boolean;
  /** Which rule of the review policy fired, when review is required. */
  needs_human_review_reason?: string | null;
  evidence: Array<{ source_tool: string; source_value: string }>;
  mitre_technique: string;
  recommended_actions: string[];
  limitations: string[];
  grounding_check?: GroundingCheck;
  shap_explanation?: ShapExplanation | null;
  flow_record?: FlowRecord | null;
  tool_call_events?: Array<{ tool: string; kwargs: Record<string, string>; status: string; timestamp: number }>;
}
