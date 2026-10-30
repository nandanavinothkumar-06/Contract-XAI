from typing import List, Optional
from pydantic import BaseModel

class ContextMetadata(BaseModel):
    target_clause_id: str
    source_document_id: str
    context_strategy: str
    context_clause_ids: List[str]
    included_context_clause_ids: List[str]
    excluded_context_clause_ids: List[str]
    target_position: int
    context_truncated: bool
    target_truncated: bool
    target_model_input_start: int
    target_model_input_end: int
    target_source_start: int
    target_source_end: int

class ContextComponent(BaseModel):
    clause_id: str
    source_document_id: str
    role: str # TARGET, PREVIOUS, NEXT, PARENT, CHILD, WINDOW
    order: int
    source_start: int
    source_end: int
    model_input_start: int
    model_input_end: int
    text: str

class ContextualizedInput(BaseModel):
    target_clause_id: str
    components: List[ContextComponent]
    text: str
    metadata: ContextMetadata
