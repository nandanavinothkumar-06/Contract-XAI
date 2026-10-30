from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from src.review.provenance import ReviewDecision
from src.abstention.schema import UncertaintySignals, AbstentionState

class PredictionContext(BaseModel):
    """
    Immutable representation of the model finding passed to the reviewer.
    """
    prediction_id: str
    source_document_id: str
    clause_id: str
    
    original_prediction: Any
    model_score: Optional[float] = None
    model_metadata: Optional[Dict[str, Any]] = None
    
    abstention_status: Optional[AbstentionState] = None
    uncertainty_signals: Optional[UncertaintySignals] = None
    
    evidence_ids: List[str] = []
    retrieval_ids: List[str] = []
    missing_provision_ids: List[str] = []
    legal_source_ids: List[str] = []

class ReviewRecord(BaseModel):
    """
    The output of the human review process.
    Must strictly separate human evaluation from the model prediction context.
    """
    review_id: str
    prediction_context: PredictionContext
    
    decision: ReviewDecision
    reviewer_rationale: Optional[str] = None
    reviewer_notes: Optional[str] = None
    
    # Explicit references back to the prediction context items
    referenced_evidence_ids: List[str] = []
    referenced_retrieval_ids: List[str] = []
    referenced_missing_provision_ids: List[str] = []
    referenced_legal_source_ids: List[str] = []
    
    timestamp: str
    workflow_version: str
    reviewer_id: Optional[str] = None
    
    is_test_fixture: bool = False
