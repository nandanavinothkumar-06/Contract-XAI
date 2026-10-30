from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from src.abstention.provenance import AbstentionState, AbstentionReasonCode, CalibrationStatus, PredictionType

class UncertaintySignals(BaseModel):
    prediction_id: str
    prediction_type: PredictionType
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    configuration_version: str

    top_probability: Optional[float] = None
    second_probability: Optional[float] = None
    margin: Optional[float] = None
    entropy: Optional[float] = None
    
    per_label_probabilities: Optional[Dict[str, float]] = None
    near_threshold_labels: Optional[List[str]] = None
    
    input_truncated: Optional[bool] = None
    context_incomplete: Optional[bool] = None
    
    evidence_available: Optional[bool] = None
    
    retrieval_available: Optional[bool] = None
    retrieval_top_score: Optional[float] = None
    retrieval_candidate_count: Optional[int] = None
    
    calibration_status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED

class AbstentionDecision(BaseModel):
    decision_id: str
    prediction_id: str
    status: AbstentionState
    reasons: List[AbstentionReasonCode]
    
    uncertainty_signals: UncertaintySignals
    
    policy_version: str
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    created_at: str
    
    source_document_id: Optional[str] = None
    clause_id: Optional[str] = None
    
    is_test_fixture: bool = False
