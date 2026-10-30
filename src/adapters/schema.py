from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

class TaskType(str, Enum):
    QA_SPAN_EXTRACTION = "QA_SPAN_EXTRACTION"
    MULTI_LABEL_PROVISION_CLASSIFICATION = "MULTI_LABEL_PROVISION_CLASSIFICATION"
    DOCUMENT_NLI = "DOCUMENT_NLI"
    UNFAIR_CLAUSE_DETECTION = "UNFAIR_CLAUSE_DETECTION"
    RATIONALE_EXTRACTION = "RATIONALE_EXTRACTION"
    MISSING_CLAUSE_DETECTION = "MISSING_CLAUSE_DETECTION"
    UNILATERAL_CHANGE_RISK_DETECTION = "UNILATERAL_CHANGE_RISK_DETECTION"
    CLAUSE_RISK_CLASSIFICATION = "CLAUSE_RISK_CLASSIFICATION"
    OTHER = "OTHER"

class EvidenceSpan(BaseModel):
    start: int
    end: int
    text: str
    source_field: str
    
    @field_validator('start', 'end')
    def validate_offsets(cls, v):
        if v < 0:
            raise ValueError("Offsets cannot be negative")
        return v
    
    @field_validator('end')
    def validate_end_after_start(cls, v, info):
        if 'start' in info.data and v < info.data['start']:
            raise ValueError("End offset cannot be less than start offset")
        return v

class DatasetRecord(BaseModel):
    record_id: str
    source_dataset: str
    source_version: Optional[str] = None
    source_document_id: str
    contract_id: Optional[str] = None
    clause_id: Optional[str] = None
    text: str
    task: TaskType
    original_label: Any
    normalized_label: Optional[Any] = None
    evidence: List[EvidenceSpan] = Field(default_factory=list)
    rationale: Optional[str] = None
    domain: Optional[str] = None
    language: Optional[str] = None
    annotation_source: Optional[str] = None
    source_reference: Optional[str] = None
    license_status: Optional[str] = None
    access_status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('text')
    def text_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Text cannot be empty")
        return v

    @field_validator('evidence')
    def validate_evidence_bounds(cls, v, info):
        if 'text' in info.data:
            text_len = len(info.data['text'])
            for span in v:
                if span.end > text_len:
                    # Depending on exact indexing rules of the dataset, 
                    # we might allow offset to exceed slightly, but strictly it shouldn't.
                    # Since source_field could be from full document while 'text' is clause,
                    # we should only check if source_field matches 'text'.
                    if span.source_field == 'text' and span.end > text_len:
                        raise ValueError(f"Evidence span end ({span.end}) exceeds text length ({text_len})")
        return v
