from typing import Optional, List
from pydantic import BaseModel, Field

class EvidenceSpan(BaseModel):
    evidence_id: str
    document_id: Optional[str] = None
    clause_id: Optional[str] = None
    source_start: int
    source_end: int
    text: str
    token_start: Optional[int] = None
    token_end: Optional[int] = None
    raw_score: float
    ranking_score: float
    rank: int
    method: str
    prediction_label: str
    prediction_score: float
    evidence_type: str = "MODEL_DERIVED_EVIDENCE" # MODEL_DERIVED_EVIDENCE, GROUND_TRUTH_EVIDENCE
    is_ground_truth: bool = False
    is_model_derived: bool = True
    is_human_reviewed: bool = False

class EvidenceResult(BaseModel):
    evidence_spans: List[EvidenceSpan]
    method: str
    target_label: str
    target_score: float
    truncation_status: bool = False
    alignment_status: str = "SUCCESS" # SUCCESS, FAILED
    visible_source_start: int = 0
    visible_source_end: int = -1 # -1 implies end of document or unknown limit
    is_test_fixture: bool = False
