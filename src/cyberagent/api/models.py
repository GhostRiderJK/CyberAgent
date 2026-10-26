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
    flow_id: int
    source_ip: str
    source_port: Optional[int]
    destination_ip: str
    destination_port: Optional[int]
    protocol: str
    timestamp: Optional[datetime.datetime]
    # Add any other metadata fields as needed


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
    evidence: List[Dict[str, Any]]
    mitre_technique: str
    recommended_actions: List[str]
    limitations: List[str]
    grounding_check: Optional[Dict[str, Any]] = None


class InvestigationProgress(BaseModel):
    event: str  # 'start', 'tool_call', 'end'
    flow_id: Optional[int] = None
    tool: Optional[str] = None
    kwargs: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    # For 'end' event, we might include the final investigation result
    investigation_result: Optional[InvestigationResult] = None