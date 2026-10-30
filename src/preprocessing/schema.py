from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.adapters.schema import DatasetRecord, EvidenceSpan

class ProcessedEvidenceSpan(BaseModel):
    original_start: int
    original_end: int
    processed_start: Optional[int] = None
    processed_end: Optional[int] = None
    text: str
    source_field: str
    offset_mapping_status: str = "AVAILABLE"

class TransformationLog(BaseModel):
    operation: str
    applied: bool
    description: str
    reversible: bool

class PreprocessedRecord(BaseModel):
    original_record: DatasetRecord
    processed_text: str
    evidence: List[ProcessedEvidenceSpan] = Field(default_factory=list)
    preprocessing_operations: List[TransformationLog] = Field(default_factory=list)
    quality_flags: List[str] = Field(default_factory=list)
    text_hash: str
    preprocessing_version: str = "1.0.0"
    config_hash: str
