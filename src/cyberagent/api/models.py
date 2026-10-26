from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import datetime


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime.datetime = datetime.datetime.now()


class ModelStatusResponse(BaseModel):
    model_loaded: bool
    model_type: Optional[str] = None
    feature_count: Optional[int] = None
    classes: Optional[List[str]] = None


class PredictRequest(BaseModel):
    flow_id: int


class PredictResponse(BaseModel):
    flow_id: int
    predicted_class: str
    confidence: float
    probabilities: Dict[str, float]


class FlowMetadataResponse(BaseModel):
    """Connection-level fields of a flow, read from the stored record.

    A field the dataset does not keep is null and named in `missing_fields`, so the UI
    can say "not in the record" instead of showing a made-up 0 or empty string.
    """
    flow_id: Optional[int] = None
    source_ip: Optional[str] = None
    source_port: Optional[int] = None
    destination_ip: Optional[str] = None
    destination_port: Optional[int] = None
    protocol: Optional[str] = None
    timestamp: Optional[str] = None
    missing_fields: List[str] = []
    available: bool = False
    reason: Optional[str] = None


class InvestigationToolCall(BaseModel):
    tool: str
    kwargs: Dict[str, Any]
    timestamp: datetime.datetime


class InvestigationResult(BaseModel):
    verdict: str
    predicted_class: str
    severity: str
    confidence: float
    needs_human_review: bool
    # Which rule of the review policy fired - shown next to the Yes/No in the UI.
    needs_human_review_reason: Optional[str] = None
    evidence: List[Dict[str, Any]]
    mitre_technique: str
    recommended_actions: List[str]
    limitations: List[str]
    grounding_check: Optional[Dict[str, Any]] = None
    # Structured SHAP arrays straight from explain_flow, not from the narrative.
    shap_explanation: Optional[Dict[str, Any]] = None
    flow_record: Optional[FlowMetadataResponse] = None
    tool_call_events: Optional[List[Dict[str, Any]]] = None


class InvestigationProgress(BaseModel):
    event: str  # 'start', 'tool_call', 'end'
    flow_id: Optional[int] = None
    tool: Optional[str] = None
    kwargs: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    # For 'end' event, we might include the final investigation result
    investigation_result: Optional[InvestigationResult] = None