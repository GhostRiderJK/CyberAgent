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

export interface FlowMetadataResponse {
  flow_id: number;
  src_ip: string;
  dst_ip: string;
  src_port: number;
  dst_port: number;
  protocol: string;
  timestamp: string;
  duration: number;
  total_fwd_packets: number;
  total_bwd_packets: number;
  total_len_fwd_packets: number;
  total_len_bwd_packets: number;
  fwd_packet_length_max: number;
  fwd_packet_length_min: number;
  fwd_packet_length_mean: number;
  fwd_packet_length_std: number;
  bwd_packet_length_max: number;
  bwd_packet_length_min: number;
  bwd_packet_length_mean: number;
  bwd_packet_length_std: number;
  flow_bytes_s: number;
  flow_packets_s: number;
}

export interface GroundingCheck {
  passed: boolean;
  checks: Array<{ check: string; passed: boolean; detail: string }>;
  ungrounded_numbers: string[];
}

export interface InvestigationResult {
  verdict: string;
  predicted_class: string;
  severity: string;
  confidence: number;
  needs_human_review: boolean;
  evidence: Array<{ source_tool: string; source_value: string }>;
  mitre_technique: string;
  recommended_actions: string[];
  limitations: string[];
  grounding_check?: GroundingCheck;
  tool_call_events?: Array<{ tool: string; kwargs: Record<string, string>; status: string; timestamp: number }>;
}
