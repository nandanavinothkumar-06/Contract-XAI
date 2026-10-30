from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SegmentType(str, Enum):
    DOCUMENT_TITLE = "DOCUMENT_TITLE"
    SECTION_HEADING = "SECTION_HEADING"
    CLAUSE = "CLAUSE"
    SUBCLAUSE = "SUBCLAUSE"
    PARAGRAPH = "PARAGRAPH"
    LIST_ITEM = "LIST_ITEM"
    DEFINITION = "DEFINITION"
    SCHEDULE = "SCHEDULE"
    EXHIBIT = "EXHIBIT"
    APPENDIX = "APPENDIX"
    TABLE = "TABLE"
    UNKNOWN = "UNKNOWN"

class Segment(BaseModel):
    segment_id: str
    parent_segment_id: Optional[str] = None
    segment_type: SegmentType
    text: str
    original_start: int
    original_end: int
    processed_start: Optional[int] = None
    processed_end: Optional[int] = None
    heading: Optional[str] = None
    numbering: Optional[str] = None
    level: int = 0
    path: str = ""
    sequence: int = 0
    source_dataset: str
    source_document_id: str
    contract_id: Optional[str] = None
    existing_clause_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EvidenceAssociation(BaseModel):
    evidence_index: int
    evidence_text: str
    overlapping_segment_ids: List[str]

class SegmentedDocument(BaseModel):
    document_id: str
    source_dataset: str
    source_document_id: str
    contract_id: Optional[str] = None
    segments: List[Segment] = Field(default_factory=list)
    segmentation_version: str = "1.0.0"
    segmentation_config_hash: str
    quality_flags: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    evidence_associations: List[EvidenceAssociation] = Field(default_factory=list)
